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
from daemon.pidfile import TimeoutPIDLockFile
import importlib
from lockfile.pidlockfile import PIDLockFile
import glob
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
    etc_dir = '/etc/tuclient'
    parser = argparse.ArgumentParser(description='TuneUp.ai Client daemon')
    parser.add_argument('-c', '--conf', metavar='CONF_FILE', type=str, nargs=1,
                        help='Configuration file (default to *.conf files in {etc_dir} in alphabetical order)'.format(
                            etc_dir=etc_dir))
    parser.add_argument('-p', '--pidfile', metavar='PIDFILE', type=str,
                        help='Override PID file name from the configuration file')
    parser.add_argument('--command_socket_address', metavar='CMD_ADDR', type=str,
                        help='Override the command socket address from the configuration file')
    parser.add_argument('--log_file', metavar='LOG_FILE', type=str,
                        help='Override the log file name from the configuration file')
    parser.add_argument('--node_name', metavar='NODE_NAME', type=str,
                        help='Override the node name from the configuration file')
    parser.add_argument('--api_key', metavar='API_KEY', type=str,
                        help='User\'s API key')
    args = parser.parse_args()
    if args.conf is None:
        conffiles = [f for f in glob.glob(os.path.join(etc_dir, '*.conf')) if os.path.isfile(f)]
        conffiles.sort()
    else:
        conffiles = args.conf
    config = ConfigFile(None, 'client', socket.gethostname(), *conffiles)
    if args.log_file is None:
        logger = config.get_logger()
    else:
        logger = tulogging.get_file_logger(args.log_file)

    # Configuration
    # These initial values are necessary if exception occurs in config.*()
    node_name = 'Unset'
    cluster_name = 'Unset'
    try:
        client_id = uuid1()
        try:
            node_name = args.node_name if args.node_name is not None else config.node_name()
            cluster_name = config.cluster_name()
            api_secret_key = args.api_key if args.api_key is not None else config.api_secret_key()
        except KeyError as err:
            logger.error('Required configuration {err} is not set. Exiting...'.format(err=str(err)))
            exit(2)

        # Protocol
        cmd_socket_addr = config.command_socket_address() if args.command_socket_address is None \
            else args.command_socket_address
        protocol_name = config.protocol()
        if protocol_name == 'zmq':
            protocol = ZMQProtocol(logger, client_id, config.gateway_address(), cmd_socket_addr=cmd_socket_addr)
        else:
            raise ValueError('Unsupported protocol ' + protocol_name)
        network_timeout = config.network_timeout()

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

        client = TUClient(logger, client_id, cluster_name=cluster_name, node_name=node_name, api_secret_key=api_secret_key,
                          protocol=protocol, getters=[getter], setters=[setter], network_timeout=network_timeout,
                          **tuclient_kwargs)

        pidfile_name = args.pidfile if args.pidfile is not None else config.pidfile()
        # PIDLockFile(pidfile_name, timeout=-1) doesn't work for Python 2. We
        # have to use the following:
        pidfile = TimeoutPIDLockFile(pidfile_name, acquire_timeout=-1)
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
    except Exception as err:
        logger.error('Client node {node_name} fatal error: {err_name}: {err}'
                     .format(node_name=node_name, err_name=type(err).__name__, err=str(err)))
        logger.error(traceback.format_exc())
        # Don't continue on other errors
        exit(1)

