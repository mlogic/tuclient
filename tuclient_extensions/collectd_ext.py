"""The singleton collectd extension class"""
# Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>.
# All rights reserved.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 2.1 as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see
# https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html
from __future__ import absolute_import, division, print_function, unicode_literals

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import grp
import logging
import os
import select
import socket
import subprocess
import threading
import time
import traceback
import tuclient_extensions.collectd_proto

_collectd_inst = None


class CollectdExt:
    CMD_INPROC_ADDR = 'inproc://#collectdzmqcmd'

    def __init__(self, logger, collectd_conf_template=None):
        """Create an instance of CollectdZMQ

        :param logger: the logger
        :param collectd_conf_template: overriding the default collectd conf template"""
        self._logger = logger
        self._started = False
        self._stop_requested = False
        # We use a member-wise buffer for the rare case that one socket.recv() call only
        # received a half of packet.
        self._buf = b''
        self._plugins = []
        # The last plugin from previous batch of parts received
        self._last_plugin = None
        # The last ts from the previous batch of parts received
        self._last_ts = None
        self._callbacks = dict()
        self._thread = None
        if collectd_conf_template is None:
            self._collectd_conf_template = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                        'collectd_template.conf')
        else:
            self._collectd_conf_template = collectd_conf_template

        if os.geteuid() == 0:
            if 'SNAP_DATA' in os.environ:
                snap_data_dir = os.environ['SNAP_DATA']
                self._collectd_basedir = os.path.join(snap_data_dir, 'collectd')
                logdir = self._collectd_basedir
                self._in_snap = True
            else:
                self._collectd_basedir = '/var/run/tuclient'
                logdir = '/var/log/tuclient'
                self._in_snap = False
        else:
            self._collectd_basedir = '/tmp/tuclient'
            logdir = self._collectd_basedir
            self._in_snap = False

        if not os.access(self._collectd_basedir, os.F_OK):
            os.mkdir(self._collectd_basedir)
        if not os.access(logdir, os.F_OK):
            os.mkdir(logdir)
        collectd_log_file_path = os.path.join(logdir, 'collectd.log')

        self._collectd_log_file = open(collectd_log_file_path, 'w+')
        self._collectd_conf_file_path = os.path.join(self._collectd_basedir, 'collectd.conf')

    def add_plugin(self, plugin, options=None):
        self._plugins.append((plugin, options))

    def register_callback(self, plugin_name, callback):
        """Register a callback function

        This callback function will be called when packets from the matching
        plugin_name are received from collectd, in a separate worker thread.
        So this callback function needs some synchronization mechanism if it
        is sharing data with other codes."""
        if plugin_name not in self._callbacks:
            self._callbacks[plugin_name] = []
        self._callbacks[plugin_name].append(callback)

    def _start_collectd(self):
        # type: () -> subprocess.Popen
        if self._in_snap:
            collectd_bin = os.path.join(os.environ['SNAP'], 'usr/sbin/collectd')
        else:
            collectd_bin = '/usr/sbin/collectd'
        self._logger.info('Creating a collectd subprocess using binary ' + collectd_bin)
        return subprocess.Popen([collectd_bin, '-f', '-C', self._collectd_conf_file_path],
                                stdout=self._collectd_log_file, stderr=self._collectd_log_file)

    def _gen_collectd_conf_file(self):
        plugin_conf = ''
        for plugin in self._plugins:
            if plugin[1] is None:
                # This plugin needs no option
                plugin_conf += 'LoadPlugin "{plugin}"\n'.format(plugin=plugin[0])
            else:
                plugin_conf += '''LoadPlugin "{plugin}"
<Plugin "{plugin}">
    {option}
</Plugin>'''.format(plugin=plugin[0], option=plugin[1])

        with open(self._collectd_conf_template) as f:
            conf_str = f.read()
            conf_str = conf_str.replace('{% plugins %}', plugin_conf)
            conf_str = conf_str.replace('{% basedir %}', self._collectd_basedir)
            conf_str = conf_str.replace('{% usergroup %}', grp.getgrgid(os.getegid())[0])
            if self._in_snap:
                conf_str = conf_str.replace('{% plugindir %}', os.path.join(os.environ['SNAP'], 'usr/lib/collectd'))
                conf_str = conf_str.replace('{% typesdb %}', os.path.join(os.environ['SNAP'],
                                                                          'usr/share/collectd/types.db'))
            else:
                conf_str = conf_str.replace('{% plugindir %}', '/usr/lib/collectd')
                conf_str = conf_str.replace('{% typesdb %}', '/usr/share/collectd/types.db')

        with open(self._collectd_conf_file_path, 'w') as f:
            f.write(conf_str)

    def _recv_all_from_sock(self, sock):
        result = b''
        while True:
            rlist, _, xlist = select.select([sock], [], [sock], 0)
            if sock in xlist:
                raise IOError('collectd sock got exception')
            if sock in rlist:
                # We just put a not-too-small arbitrary number here
                buf = sock.recv(65536)
                self._logger.debug(f'Received a packet of {len(buf)} bytes')
                result += buf
            else:
                return result

    def _process_packet(self, parts):
        # Packets are separated by the Host part.
        host = None
        parts_for_plugins = dict()
        # A list of parts that we will be adding to a specific plugin's buffer
        pending_parts = []

        for part_type, part_data in parts:
            if part_type == tuclient_extensions.collectd_proto.PART_TYPE_HOST:
                assert isinstance(part_data, str)
                host = part_data
            elif part_type == tuclient_extensions.collectd_proto.PART_TYPE_PLUGIN:
                assert isinstance(part_data, str)
                self._last_plugin = part_data
                # When switching to sending parts to another plugin, we always prepend the parts
                # with the current ts, because the new plugin requires the ts and collectd omits
                # sending out ts when the ts is the same as ts from the previous plugin.
                if self._last_ts is not None:
                    pending_parts.append((tuclient_extensions.collectd_proto.PART_TYPE_TIME_HR, self._last_ts))
            elif part_type == tuclient_extensions.collectd_proto.PART_TYPE_TIME_HR:
                assert isinstance(part_data, float)
                self._last_ts = part_data

            # Add this part to per-plugin dict
            if self._last_plugin is None:
                pending_parts.append((part_type, part_data))
            else:
                if len(pending_parts) > 0:
                    new_data = pending_parts + [(part_type, part_data)]
                    pending_parts = []
                else:
                    new_data = [(part_type, part_data)]
                if self._last_plugin in parts_for_plugins:
                    parts_for_plugins[self._last_plugin].extend(new_data)
                else:
                    parts_for_plugins[self._last_plugin] = new_data

        for plugin, parts in parts_for_plugins.items():
            if plugin in self._callbacks:
                for cb in self._callbacks[plugin]:
                    cb(host, plugin, parts)
            else:
                self._logger.warning(f'Received data from plugin {plugin} but not callbacks registered for it')

    def _thread_func(self):
        listen_addr = '127.0.0.1'
        listen_port = 7779

        self._gen_collectd_conf_file()
        collectd_proc = None
        collectd_socket = None
        try:
            collectd_proc = self._start_collectd()
            self._logger.info('collectd subprocess is started')
            family, socktype, proto, canonname, sockaddr = socket.getaddrinfo(listen_addr,
                                                                              listen_port,
                                                                              socket.AF_UNSPEC,
                                                                              socket.SOCK_DGRAM,
                                                                              0,
                                                                              socket.AI_PASSIVE)[0]
            collectd_socket = socket.socket(family, socktype, proto)
            collectd_socket.setblocking(False)
            collectd_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            collectd_socket.bind(sockaddr)
            self._logger.info('collectd listener is started')
            self._started = True

            while not self._stop_requested:
                rlist, _, _ = select.select([collectd_socket], [], [], 1)
                if collectd_socket in rlist:
                    self._buf += self._recv_all_from_sock(collectd_socket)
                    parts, self._buf = tuclient_extensions.collectd_proto.parse_parts(self._buf)
                    self._process_packet(parts)

                # Monitor the status of our collectd subprocess
                if collectd_proc.poll() is not None:
                    self._logger.error("collectd subprocess is terminated with return code {returncode}. ".
                                       format(returncode=collectd_proc.returncode) +
                                       "Check collectd's log in {collectd_basedir} for more information. ".
                                       format(collectd_basedir=self._collectd_basedir) +
                                       "Stopping the collectd listener...")
                    # For now we just quit. Maybe we should try to restart collectd, but
                    # it is not clear that there's any beneficial to that before someone
                    # could check collectd's log and fix the underlying issue.
                    self._stop_requested = True

            self._logger.info('collectd listener stopped')
        except Exception as err:
            self._logger.error('Fatal error in collectd_ext: {error_name}: {error_str}'.
                               format(error_name=type(err).__name__, error_str=str(err)))
            self._logger.error(traceback.format_exc())
            raise err
        finally:
            if collectd_proc is not None:
                self._logger.debug('Sending SIGTERM to the collectd subprocess...')
                collectd_proc.terminate()
            if collectd_socket is not None:
                collectd_socket.close()
            if collectd_proc is not None:
                self._logger.info('Waiting for the collectd subprocess to stop...')
                collectd_proc.wait()
                self._logger.info('The collectd subprocess is stopped.')
            self._started = False

    def start(self):
        if self._thread is None:
            self._logger.debug('Starting a new collectd_ext thread...')
            self._thread = threading.Thread(target=self._thread_func)
            self._thread.start()
            while not self._started:
                time.sleep(0.001)
                if not self._thread.is_alive():
                    raise RuntimeError('Starting collectd_ext thread failed.')
        else:
            self._logger.debug('A collectd_ext thread is already running')

    def stop(self):
        if self.is_alive():
            self._stop_requested = True
            self._thread.join()
            self._thread = None

    def is_alive(self):
        return self._started

    def __del__(self):
        self._collectd_log_file.close()
        if self._thread is not None:
            self._thread.join()
            self._thread = None


def get_collectd_ext_instance(logger):
    # type: (logging.Logger) -> CollectdExt
    global _collectd_inst
    if _collectd_inst is None:
        logger.debug('Creating a new CollectdExt instance')
        _collectd_inst = CollectdExt(logger)
    else:
        logger.debug('Reusing the existing CollectdExt instance')
    return _collectd_inst


def destroy_collectd_ext_instance():
    """Destroy the global collectd_ext instance

    This function is used to destroy the global collectd_ext instance that was
    created by get_collectd_ext_instance(). You don't need to call this if your
    program is exiting normally. This is usually only needed by test cases who
    need to create and destroy multiple collectd_ext instance."""
    global _collectd_inst
    _collectd_inst.stop()
    _collectd_inst = None
