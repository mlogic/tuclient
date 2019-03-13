#!/usr/bin/env python
"""Unit tests for the collectd_nginx plugin"""
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
import tuclient
from tuclient_extensions.collectd_nginx import *
import unittest


class MockCollectd:
    def add_plugin(self, plugin, options=None):
        del plugin, options
        pass

    def register_callback(self, plugin, callback):
        del plugin, callback
        pass

    def start(self):
        pass

    def stop(self):
        pass


class TestCollectdNGINX(unittest.TestCase):
    def setUp(self):
        self._logger = tuclient.get_stdout_logger()
        self._logger.setLevel(logging.WARNING)

    def _test_start_stop(self):
        """Test collecting data from an NGINX instance

        You need an NGINX server to run this test. You can start one by
        using start_test_nginx_docker.sh."""
        collectd_nginx = None
        try:
            mock_config = {'collectd_nginx_status_url':
                           'http://localhost:8080/status'}
            collectd_nginx = CollectdNGINX(self._logger, 'host1', config=ConfigBase(default=mock_config))
            collectd_nginx.start()
            self.assertListEqual(['host1/nginx/connections_accepted', 'host1/nginx/connections_failed',
                                  'host1/nginx/connections_handled', 'host1/nginx/nginx_connections_active',
                                  'host1/nginx/nginx_connections_reading', 'host1/nginx/nginx_connections_waiting',
                                  'host1/nginx/nginx_connections_writing', 'host1/nginx/nginx_requests'],
                                 collectd_nginx.pi_names)
            num_pis = len(collectd_nginx.pi_names)
            for _ in range(3):
                self.assertEqual(num_pis, len(collectd_nginx.collect()))
        finally:
            collectd_nginx.stop()

    def test_parsing_data(self):
        collectd_nginx = None
        try:
            collectd_nginx = CollectdNGINX(self._logger, 'host1', collectd_instance=MockCollectd())
            self._records_received = 0
            collectd_nginx.start()
            collectd_nginx._on_receiving_nginx_data('host1', 'nginx',
                                                    [(0, 'freesia'), (8, 1552443773.4047103), (9, 1073741824),
                                                     (2, 'nginx'), (4, 'nginx_connections'), (5, 'active'),
                                                     (6, [(1, 1.0)]), (8, 1552443773.404723), (4, 'connections'),
                                                     (5, 'handled'), (6, [(2, 8)]), (8, 1552443773.404735),
                                                     (4, 'nginx_connections'), (5, 'reading'), (6, [(1, 0.0)]),
                                                     (8, 1552443773.4047387), (5, 'writing'), (6, [(1, 1.0)]),
                                                     (8, 1552443773.4047139), (4, 'connections'), (5, 'accepted'),
                                                     (6, [(2, 8)]), (8, 1552443773.404728), (5, 'failed'),
                                                     (6, [(2, 0)]), (8, 1552443773.4047298), (4, 'nginx_requests'),
                                                     (5, ''), (6, [(2, 16)]), (8, 1552443773.4047518),
                                                     (4, 'nginx_connections'), (5, 'waiting'), (6, [(1, 0.0)]),
                                                     (8, 1552443774.4029212), (4, 'connections'), (5, 'accepted'),
                                                     (6, [(2, 20)]), (8, 1552443774.4029171), (4, 'nginx_connections'),
                                                     (5, 'active'), (6, [(1, 1.0)]), (8, 1552443774.4030075),
                                                     (4, 'nginx_requests'), (5, ''), (6, [(2, 17)]),
                                                     (8, 1552443774.4030058), (4, 'connections'), (5, 'failed'),
                                                     (6, [(2, 0)]), (8, 1552443774.4031298), (4, 'nginx_connections'),
                                                     (5, 'writing'), (6, [(1, 1.0)]), (8, 1552443774.4031565),
                                                     (5, 'waiting'), (6, [(1, 0.0)]), (8, 1552443774.4030101),
                                                     (5, 'reading'), (6, [(1, 0.0)]), (8, 1552443774.4030035),
                                                     (4, 'connections'), (5, 'handled'), (6, [(2, 8)])])
            self.assertListEqual([-0.76, -1.0, -1.0, -0.98, -1.0, -1.0, -0.98, -0.98], collectd_nginx.collect())
        finally:
            if collectd_nginx is not None:
                collectd_nginx.stop()


if __name__ == '__main__':
    unittest.main()
