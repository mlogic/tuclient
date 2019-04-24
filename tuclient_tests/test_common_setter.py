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
import tuclient
from tuclient_extensions import common_setters
from tuclient_extensions.nginx import *
import unittest


class TestCommonSetter(unittest.TestCase):
    def setUp(self):
        self._logger = tuclient.get_stdout_logger()
        self._logger.setLevel(logging.WARNING)

    def test_change_config_file(self):
        tmp_nginx_conf = '/tmp/test_nginx.conf'
        copyfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_common_setter_nginx.conf',),
                 tmp_nginx_conf)
        config = tuclient.ConfigFile(None, 'tuclient', None, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                          'test_common_setter.conf', ))
        setter = common_setters.Setter(self._logger, 'host1', config)
        self.assertListEqual(['host1/nginx_worker_connections'], setter.parameter_names)
        setter.start()
        setter.action(10, [-1])
        self.assertTrue(filecmp.cmp(tmp_nginx_conf, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                 'expected_test_common_setter_nginx.conf',)))


if __name__ == '__main__':
    unittest.main()
