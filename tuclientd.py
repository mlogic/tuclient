#!/usr/bin/env python
"""TuneUp.ai Client Daemon"""
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

import argparse
import importlib
import glob
import os
import re
import signal
import socket
import sys
from tuclient import *
from tuclient_extensions import *

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
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
    etc_dir = os.environ.get('SNAP_DATA', '/etc/tuclient')
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
    parser.add_argument('--gateway_addr', metavar='GATEWAY_ADDR', type=str,
                        help='Override gateway address in config file')
    parser.add_argument('-v', '--verbose', action='store_true', help='enable verbose mode')
    args = parser.parse_args()
    if args.conf is None:
        conffiles = [f for f in glob.glob(os.path.join(etc_dir, '*.conf')) if os.path.isfile(f)]
        conffiles.sort()
    else:
        conffiles = args.conf
    host = socket.gethostname()
    config = ConfigFile(None, 'client', host, conffiles)
    if args.log_file is None:
        logger = config.get_logger()
    else:
        logger = tulogging.get_file_logger(args.log_file)
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        # Use the level set by config.get_logger() according to config file setting
        pass

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
            logger.info('Creating ZMQ protocol to listen for control command on ' + cmd_socket_addr)
            protocol = ZMQProtocol(logger, client_id,
                                   args.gateway_addr if args.gateway_addr is not None else config.gateway_address(),
                                   cmd_socket_addr=cmd_socket_addr)
        else:
            raise ValueError('Unsupported protocol ' + protocol_name)
        network_timeout = config.network_timeout()

        # Setter modules
        setters = []   # type: List[SetterExtensionBase]
        setter_module_str = config.setter_module()
        if setter_module_str is not None:
            for setter_module_name in setter_module_str.split(', '):
                logger.info('Loading setter ' + setter_module_name)
                setter_module = importlib.import_module(setter_module_name)
                setter_class = getattr(setter_module, 'Setter')
                setters.append(setter_class(logger, host, config))
                logger.info('Finished loading setter ' + setter_module_name)
        else:
            logger.info('No setter is set')

        # Getter modules
        getters = []    # type: List[GetterExtensionBase]
        getter_module_str = config.getter_module()
        if getter_module_str is not None:
            for getter_module_name in getter_module_str.split(', '):
                logger.info('Loading getter ' + getter_module_name)
                getter_module = importlib.import_module(getter_module_name)
                getter_class = getattr(getter_module, 'Getter')
                getters.append(getter_class(logger, host, config))
                logger.info('Finished loading getter ' + getter_module_name)
        else:
            logger.info('No getter is set')

        if len(setters) + len(getters) == 0:
            logger.error('Setter and getter are both empty. You have to set at least one setter or getter.')
            exit(2)

        # It's ok for either setter or getter to be empty. The other required data
        # can be from other nodes in the same cluster.

        # Start the setters and getters once they are all created. This is necessary
        # for collectd-related getters to get pi_names before we could create a
        # TuningGoalCalculator below.
        pi_names = []
        for getter in getters:
            logger.info('Starting getter' + (' ' + getter.name) if getter.name != '' else '')
            getter.start()
            pi_names += getter.pi_names
            logger.info('Getter' + (' ' + getter.name) if getter.name != '' else '' + ' is started')
        for setter in setters:
            logger.info('Starting setter' + (' ' + setter.name) if setter.name != '' else '')
            setter.start()
            logger.info('Setter' + (' ' + setter.name) if setter.name != '' else '' + ' is started')

        # tick_len
        tuclient_kwargs = dict()
        if 'tick_len' in config.get_config():
            tuclient_kwargs['tick_len'] = config.tick_len()

        # tuning_goal
        tuning_goal_regex = config.tuning_goal_regex()
        if tuning_goal_regex is None:
            raise ValueError('tuning_goal_regex is not set.')

        logger.info('Creating the client instance')
        # Always start sending PI right away. In the future we can add an argument to tuclientd.py to disable
        # this if necessary.
        client = TUClient(logger, client_id, cluster_name=cluster_name, node_name=node_name,
                          api_secret_key=api_secret_key, protocol=protocol, getters=getters, setters=setters,
                          network_timeout=network_timeout, tuning_goal_name=tuning_goal_regex,
                          tuning_goal_calculator=TuningGoalCalculatorRegex(logger, config, pi_names, tuning_goal_regex),
                          sending_pi_right_away=True, **tuclient_kwargs)
        logger.info('Client instance is created')

        pidfile_name = args.pidfile if args.pidfile is not None else config.pidfile()
        if pidfile_name is not None:
            # If a pidfile is set, we start as a traditional daemon.
            import daemon
            from daemon.pidfile import TimeoutPIDLockFile
            from lockfile.pidlockfile import PIDLockFile

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
                signal.SIGINT: stop,
                signal.SIGHUP: 'terminate',
                # signal.SIGUSR1: reload_program_config,
            }

            context.files_preserve = [tulogging._log_file_handler.stream]

            with context:
                logger.info('Starting the client instance')
                client.start()
        else:
            # If a pidfile is not set, we start as a simple program.
            logger.info('Starting the client instance')
            client.start()
    except Exception as err:
        logger.error('Client node {node_name} fatal error: {err_name}: {err}'
                     .format(node_name=node_name, err_name=type(err).__name__, err=str(err)))
        logger.error(traceback.format_exc())
        # Don't continue on other errors
        exit(1)
