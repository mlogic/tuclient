#!/usr/bin/env python
"""TuneUp.ai Client Daemon"""
# Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>.
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

import argparse
import daemon
import importlib.util
from lockfile.pidlockfile import PIDLockFile
import os
import signal
import socket
import sys
from tuclient import *
from tuclient_extensions import *

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

client = None


def check_stale_lock(pidfile):
    pidfile_pid = pidfile.read_pid()
    if pidfile_pid is not None:
        try:
            os.kill(pidfile_pid, signal.SIG_DFL)
        except ProcessLookupError as exc:
            # The specified PID does not exist
            pidfile.break_lock()
            return
        print("Process is already running")
        exit(255)
    return


def stop(signum, frame):
    if client:
        client.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TuneUp.ai Client daemon')
    parser.add_argument('-c', '--conf', metavar='CONF_FILE', type=str, nargs=1,
                        help='Configuration file.')
    parser.add_argument('-p', '--pidfile', metavar='PIDFILE', type=str, nargs=1,
                        help='PID file name')
    args = parser.parse_args()
    config = ConfigFile(None, 'client', socket.gethostname(), args.conf)
    logger = config.get_logger()

    # ID
    client_id = uuid1()
    node_name = config.node_name()
    cluster_name = config.cluster_name()

    # Protocol
    protocol_name = config.protocol()
    if protocol_name == 'zmq':
        protocol = ZMQProtocol(logger, client_id, config.gateway_address())
    else:
        raise ValueError('Unsupported protocol ' + protocol_name)

    # Setter module
    setter_module = importlib.import_module(config.setter_module())
    setter_class = getattr(setter_module, 'Setter')
    setter = setter_class(logger, config)

    # Getter module
    getter_module = importlib.import_module(config.getter_module())
    getter_class = getattr(setter_module, 'Getter')
    getter = getter_class(logger, config)

    # tick_len
    tuclient_kwargs = dict()
    if 'tick_len' in config.get_config():
        tuclient_kwargs['tick_len'] = config.tick_len()

    client = TUClient(logger, client_id, cluster_name=cluster_name, node_name=node_name, protocol=protocol,
                      getters=[getter], setters=[setter], **tuclient_kwargs)

    pidfile_name = config.pidfile()
    pidfile = PIDLockFile(pidfile_name, timeout=-1)
    check_stale_lock(pidfile)
    daemon_output_dir = config.daemon_output_dir()
    context = daemon.DaemonContext(
        # working_directory='/var/lib/foo',
        pidfile=pidfile,
        stdout=open(os.path.join(daemon_output_dir, 'tuclient_{name}_stdout'.format(name=node_name)), 'w+'),
        stderr=open(os.path.join(daemon_output_dir, 'tuclient_{name}_stderr'.format(name=node_name)), 'w+'),
    )

    context.signal_map = {
        signal.SIGTERM: stop,
        signal.SIGHUP: 'terminate',
        # signal.SIGUSR1: reload_program_config,
    }

    context.files_preserve = [tulogging._log_file_handler.stream]

    with context:
        client.start()
