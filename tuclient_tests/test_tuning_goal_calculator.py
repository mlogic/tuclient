#!/usr/bin/env python
"""Unit tests for TuningGoalCalculator classes
"""
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
import os
import sys
from tuclient import ConfigFile, TuningGoalCalculatorRegex
import unittest


class TestTuningGoalCalculator(unittest.TestCase):
    def __init__(self, methodName):
        super(TestTuningGoalCalculator, self).__init__(methodName)
        self._logger = logging.getLogger()
        self._logger.addHandler(logging.StreamHandler(sys.stdout))
        self._config = ConfigFile(self._logger, None, None,
                                  os.path.join(os.path.dirname(os.path.abspath(__file__)), '../tuclient/default.conf'))

    def test_matching_one_pi(self):
        pi_names = ['host1/nginx/connections_accepted', 'host1/nginx/connections_failed',
                    'host1/nginx/connections_handled', 'host1/nginx/nginx_connections_active',
                    'host1/nginx/nginx_connections_reading', 'host1/nginx/nginx_connections_waiting',
                    'host1/nginx/nginx_connections_writing', 'host1/nginx/nginx_requests']
        pis = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        tgc = TuningGoalCalculatorRegex(self._logger, self._config, pi_names, 'nginx/connections_accepted')
        self.assertAlmostEqual(0.1, tgc.get_tuning_goal(pis))

    def test_matching_multiple_pis(self):
        pi_names = ['host1/nginx/connections_accepted', 'host1/nginx/connections_failed',
                    'host1/nginx/connections_handled', 'host1/nginx/nginx_connections_active',
                    'host1/nginx/nginx_connections_reading', 'host1/nginx/nginx_connections_waiting',
                    'host1/nginx/nginx_connections_writing', 'host1/nginx/nginx_requests']
        pis = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        tgc = TuningGoalCalculatorRegex(self._logger, self._config, pi_names, 'nginx/connections')
        self.assertAlmostEqual((0.1+0.2+0.3)/3, tgc.get_tuning_goal(pis))


if __name__ == '__main__':
    unittest.main()
