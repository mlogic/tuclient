#!/usr/bin/env python
"""Unit tests for the ZMQProtocol class
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
import os
import sys
from tuclient import *
import unittest
from tuclient_extensions.zmq_protocol import ZMQProtocol
# This file has to be Python 2/3 compatible
try:
    from queue import Queue
except ImportError:
    from Queue import Queue


class TestZMQProtocol(unittest.TestCase):
    def test_start_stop(self):
        """Test start stop"""
        logger = logging.getLogger()
        logger.addHandler(logging.StreamHandler(sys.stdout))
        logger.setLevel(logging.WARNING)
        client1_id = uuid1()
        zp = ZMQProtocol(logger=logger, client_id=client1_id, gateway_address='127.0.0.1:7777')
        msg_queue = Queue()
        zp.set_target_queue(msg_queue)
        # Must support start/stop for more than once
        for _ in range(4):
            self.assertEqual(False, zp.started)
            zp.start_poller()
            start_time = time.time()
            while not zp.started:
                if time.time() - start_time > 1:
                    # Timeout
                    self.assertEqual(True, zp.started)
                    break
            self.assertEqual(True, zp.started)
            zp.disconnect()
            self.assertEqual(False, zp.started)

