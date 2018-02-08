#!/usr/bin/env python
"""Unit tests for Config classes
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
from tuclient import ConfigFile
import unittest


class TestConfig(unittest.TestCase):
    def test_parsing_conf_file(self):
        logger = logging.getLogger()
        logger.addHandler(logging.StreamHandler(sys.stdout))
        config = ConfigFile(logger, None, None, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_conf_file.ini', ))
        self.assertEqual('mongodb', config.db_type())
        self.assertEqual('/home/tsg/dbfile', config.db_path())
        # The values in this config file's [DEFAULT] section should overwrite the values
        # from the default config file.
        self.assertEqual('/var/log/my_tu_log_file', config.log_file())
        self.assertEqual(logging.DEBUG, config.logging_level())

    def test_overriding_config(self):
        config = ConfigFile(None, 'gateway', None, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_conf_file.ini', ))
        self.assertEqual('/var/log/tugateway/log', config.log_file())
        self.assertEqual(logging.DEBUG, config.logging_level())

        config = ConfigFile(None, 'client', 'host_1', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_conf_file.ini', ))
        self.assertEqual('/var/log/tuclient_host_1/log', config.log_file())
        # client.host_1 doesn't logging_level, so the value in [client] should be used, not the value in [DEFAULT].
        self.assertEqual(logging.INFO, config.logging_level())

        # host_x doesn't exist
        config = ConfigFile(None, 'client', 'host_x', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_conf_file.ini', ))
        self.assertEqual('/var/log/tuclient/log', config.log_file())
        self.assertEqual(logging.INFO, config.logging_level())

    def test_empty_config_file(self):
        config = ConfigFile(None, 'gateway', None, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_conf_file_empty.ini', ))
        # Default values from tuclient/default_conf_file.ini should be used here
        self.assertEqual('/var/log/tu/log', config.log_file())
        self.assertEqual(logging.WARNING, config.logging_level())


if __name__ == '__main__':
    unittest.main()
