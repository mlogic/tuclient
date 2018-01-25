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
        config = ConfigFile(logger, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_conf_file.ini', ))
        self.assertEqual('mongodb', config.db_type())
        self.assertEqual('/home/tsg/dbfile', config.db_path())


if __name__ == '__main__':
    unittest.main()
