#!/usr/bin/env python
"""Unit tests for the common setter"""
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

from configparser import ConfigParser
import filecmp
import logging
from shutil import copyfile
import sys
from threading import Thread
import time
import tuclient
from tuclient import ClientStatus, monotonic_time, run_shell_command
from tuclient_extensions import common_setters, param_value_from_set, ZMQProtocol
from tuclient_extensions.nginx import *
from tuclient_tests import MockTUGateway
import unittest
from uuid import uuid1


class TestCommonSetter(unittest.TestCase):
    def setUp(self):
        self._logger = tuclient.get_stdout_logger()
        self._logger.setLevel(logging.WARNING)
        self._tmp_nginx_conf = '/tmp/test_nginx.conf'
        copyfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_common_setter_nginx.conf',),
                 self._tmp_nginx_conf)
        self._tuclient_config = tuclient.ConfigFile(None, 'tuclient', None,
                                                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                 'test_common_setter.conf', ))

    def test_change_config_file(self):
        setter = common_setters.Setter(self._logger, 'host1', self._tuclient_config)
        self.assertListEqual(['host1/nginx_open_file_cache', 'host1/nginx_sendfile/on',
                              'host1/nginx_sendfile/off', 'host1/nginx_worker_connections'], setter.parameter_names)
        setter.start()
        setter.action(10, [0, 0.4, 0.5, -1])
        self.assertTrue(filecmp.cmp(self._tmp_nginx_conf, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                       'expected_test_common_setter_nginx.conf',)))

    @staticmethod
    def _wait_for_file(expected_file, actual_file):
        start_ts = monotonic_time()
        while True:
            time.sleep(0.1)
            if filecmp.cmp(expected_file, actual_file):
                return
            if monotonic_time() - start_ts > 5:
                print('Timeout. Client1 failed to change the NGINX config file.')
                os._exit(1)

    def test_nginx_setter_with_tugateway(self):
        """Test the NGINX setter with a tugateway"""
        gateway_addr = 'tcp://127.0.0.1:7777'
        with MockTUGateway(self._logger, gateway_addr, action_len=1) as gw:
            client1_id = uuid1()
            cluster_name = 'test_cluster'
            client1_node_name = 'client1'
            client1 = tuclient.TUClient(self._logger, client1_id, cluster_name=cluster_name,
                                        node_name=client1_node_name, api_secret_key='mock key',
                                        protocol=ZMQProtocol(self._logger, client1_id, gateway_addr),
                                        getters=[], setters=[common_setters.Setter(self._logger, 'host1',
                                                                                   self._tuclient_config)],
                                        network_timeout=5, tuning_goal_name=None, tuning_goal_calculator=None)
            client1_thread = Thread(target=client1.start)
            client1_thread.start()
            try:
                # Create a controller to talk to client1
                client1_controller_uuid = uuid1()
                client1_controller = ZMQProtocol(self._logger, client1_controller_uuid)
                client1_status = client1_controller.client_status()[3]
                self.assertIn(client1_status, [ClientStatus.ALL_OK, ClientStatus.OFFLINE,
                                               ClientStatus.HANDSHAKE1_AUTHENTICATING,
                                               ClientStatus.HANDSHAKE2_UPLOAD_METADATA])
                start_ts = monotonic_time()
                while client1_controller.client_status()[3] != ClientStatus.ALL_OK:
                    if monotonic_time() - start_ts > 5:
                        print('Timeout. Client1 failed to come online.')
                        os._exit(1)

                # Send first action
                gw.action_data = [0.8, 1, -1, 0.9]
                gw.do_an_action = True
                self._wait_for_file(self._tmp_nginx_conf,
                                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 'expected_test_common_setter_nginx_with_tugateway.conf', ))

                # Send second action
                gw.action_data = [-0.5, -0.5, 0, 0.15]
                gw.do_an_action = True
                self._wait_for_file(self._tmp_nginx_conf,
                                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 'expected_test_common_setter_nginx_with_tugateway_step2.conf', ))
            finally:
                client1.stop()
                client1_thread.join()

    def test_param_value_from_set(self):
        self.assertEqual('tue',
                         param_value_from_set(['sun', 'mon', 'tue', 'wed'], 3, [-1, 0, 0.5, 0.1, 0.2, 0.3, -0.1, 0.4]))


if __name__ == '__main__':
    unittest.main()
