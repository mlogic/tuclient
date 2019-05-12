#!/usr/bin/env python
"""Unit tests for the collectd_ext extension"""
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

import logging
import tuclient
from tuclient_extensions.collectd_ext import get_collectd_ext_instance, destroy_collectd_ext_instance
import tuclient_extensions.collectd_os
import tuclient_extensions.collectd_nginx
import unittest


class TestCollectdExt(unittest.TestCase):
    def setUp(self):
        self._logger = tuclient.get_stdout_logger()
        self._logger.setLevel(logging.WARNING)
        self._collectd_ext = get_collectd_ext_instance(self._logger)

    def test_parsing_data_multiple_source(self):
        """Test parsing data when there are data from both OS and NGINX source"""
        collectd_os = tuclient_extensions.collectd_os.Getter(self._logger, 'host_a',
                                                             collectd_instance=self._collectd_ext)
        collectd_nginx = tuclient_extensions.collectd_nginx.Getter(self._logger, 'host_a',
                                                                   collectd_instance=self._collectd_ext)
        self._records_received = 0
        self._collectd_ext._process_packet([(0, 'ubuntu-bionic'), (8, 1557636779.7582574), (9, 1073741824), (2, 'nginx'), (4, 'nginx_connections'), (5, 'active'), (6, [(1, 1.0)]), (8, 1557636779.758263), (4, 'connections'), (5, 'accepted'), (6, [(2, 4103)]), (8, 1557636779.7582653), (5, 'handled'), (6, [(2, 4103)]), (8, 1557636779.7582667), (5, 'failed'), (6, [(2, 0)]), (8, 1557636779.7582712), (4, 'nginx_requests'), (5, ''), (6, [(2, 409645)]), (8, 1557636779.7582731), (4, 'nginx_connections'), (5, 'reading'), (6, [(1, 0.0)]), (8, 1557636779.7582734), (5, 'writing'), (6, [(1, 1.0)]), (8, 1557636779.7582736), (5, 'waiting'), (6, [(1, 0.0)]), (8, 1557636780.74744), (2, 'nginx'), (3, ''), (4, 'nginx_connections'), (5, 'active'), (6, [(1, 1.0)]), (8, 1557636780.752279), (4, 'connections'), (5, 'accepted'), (6, [(2, 4103)]), (8, 1557636780.7522812), (5, 'handled'), (6, [(2, 4103)])])
        self._collectd_ext._process_packet([(2, 'cpu'), (3, '0'), (4, 'cpu'), (5, 'user'), (6, [(2, 973)]), (8, 1557636780.7474453), (5, 'system'), (6, [(2, 3315)]), (8, 1557636780.747447), (5, 'wait'), (6, [(2, 441)]), (8, 1557636780.7474484), (5, 'nice'), (6, [(2, 71)]), (8, 1557636780.7474515), (5, 'interrupt'), (6, [(2, 0)]), (8, 1557636780.7474532), (5, 'softirq'), (6, [(2, 1501)]), (8, 1557636780.7474535), (5, 'steal'), (6, [(2, 0)]), (8, 1557636780.747454), (5, 'idle'), (6, [(2, 1130581)]), (8, 1557636780.7522748)])
        self._collectd_ext._process_packet([(0, 'ubuntu-bionic'), (8, 1557636780.7522829), (9, 1073741824), (2, 'nginx'), (4, 'connections'), (5, 'failed'), (6, [(2, 0)]), (8, 1557636780.752287), (4, 'nginx_connections'), (5, 'reading'), (6, [(1, 0.0)]), (8, 1557636780.75229), (5, 'writing'), (6, [(1, 1.0)]), (8, 1557636780.7522902), (5, 'waiting'), (6, [(1, 0.0)]), (8, 1557636780.7522848), (4, 'nginx_requests'), (5, ''), (6, [(2, 409646)]), (8, 1557636781.7475564), (2, 'nginx'), (3, ''), (4, 'nginx_connections'), (5, 'active'), (6, [(1, 1.0)]), (8, 1557636781.75247), (4, 'connections'), (5, 'accepted'), (6, [(2, 4103)]), (8, 1557636781.7524724), (5, 'handled'), (6, [(2, 4103)]), (8, 1557636781.752474), (5, 'failed'), (6, [(2, 0)]), (8, 1557636781.752476), (4, 'nginx_requests'), (5, ''), (6, [(2, 409647)])])
        self._collectd_ext._process_packet([(2, 'cpu'), (3, '0'), (4, 'cpu'), (5, 'user'), (6, [(2, 973)]), (8, 1557636781.7475615), (5, 'system'), (6, [(2, 3315)]), (8, 1557636781.7475631), (5, 'wait'), (6, [(2, 441)]), (8, 1557636781.7475648), (5, 'nice'), (6, [(2, 71)]), (8, 1557636781.7475665), (5, 'interrupt'), (6, [(2, 0)]), (8, 1557636781.747568), (5, 'softirq'), (6, [(2, 1501)]), (8, 1557636781.7475681), (5, 'steal'), (6, [(2, 0)]), (8, 1557636781.7475688), (5, 'idle'), (6, [(2, 1130680)]), (8, 1557636781.7524498)])

        self.assertListEqual([1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0], collectd_os.collect())

    def tearDown(self):
        destroy_collectd_ext_instance()


if __name__ == '__main__':
    unittest.main()
