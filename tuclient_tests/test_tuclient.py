#!/usr/bin/env python
"""Unit tests for the tuclient class
"""
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

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import logging
from tuclient_tests import MockTUGateway
import os
import sys
from threading import Thread
from tuclient import *
from tuclient_extensions import ZMQProtocol
import unittest


class TestTUClient(unittest.TestCase):
    def test_start_stop(self):
        """Test start stop
        """
        logger = logging.getLogger()
        logger.addHandler(logging.StreamHandler(sys.stdout))
        logger.setLevel(logging.WARNING)

        gateway_addr = '127.0.0.1:7777'
        with MockTUGateway(logger, gateway_addr):
            client1_id = uuid1()
            cluster_name = 'test_cluster'
            client1_node_name = 'client1'
            client1 = TUClient(logger, client1_id, cluster_name=cluster_name, node_name=client1_node_name,
                               api_secret_key='mock key', protocol=ZMQProtocol(logger, client1_id, gateway_addr),
                               getters=[], setters=[], network_timeout=5)
            client1_thread = Thread(target=client1.start)
            client1_thread.start()
            # Create a controller to talk to client1
            client1_controller_uuid = uuid1()
            client1_controller = ZMQProtocol(logger, client1_controller_uuid)
            client1_status = client1_controller.status()
            self.assertIn(client1_status, [ClientStatus.ALL_OK, ClientStatus.OFFLINE,
                                           ClientStatus.HANDSHAKE1_AUTHENTICATING,
                                           ClientStatus.HANDSHAKE2_UPLOAD_METADATA])
            start_ts = monotonic_time()
            while client1_controller.status() != ClientStatus.ALL_OK:
                if monotonic_time() - start_ts > 5:
                    print('Timeout. Client1 failed to come online.')
                    os._exit(1)

            client1.stop()
            client1_thread.join()
