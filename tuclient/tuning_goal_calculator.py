"""TuningGoalCalculatorBase class"""
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
from typing import List, Optional

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import abc
from .configbase import ConfigBase
import logging
import re


class TuningGoalCalculatorBase:
    __metaclass__ = abc.ABCMeta

    def __init__(self, logger, config, pi_names, tuning_goal_names):
        # type: (logging.Logger, ConfigBase, List[str], str) -> None
        self._logger = logger
        self._config = config
        self._pi_names = pi_names
        self._tuning_goal_names = tuning_goal_names

    @abc.abstractmethod
    def get_tuning_goal(self, pis):
        # type: (List[float]) -> float
        pass


class TuningGoalCalculatorRegex(TuningGoalCalculatorBase):
    def __init__(self, logger, config, pi_names, tuning_goal_names):
        # type: (logging.Logger, ConfigBase, List[str], str) -> None
        super(TuningGoalCalculatorRegex, self).__init__(logger, config, pi_names, tuning_goal_names)
        # We treat tuning_goal_names as a regex. Find all those that match from pi_names.
        prog = re.compile(tuning_goal_names)
        self._tuning_goal_pi_index = []
        for pi_name, index in zip(pi_names, range(len(pi_names))):
            if prog.search(pi_name) is not None:
                self._tuning_goal_pi_index += [index]
        if len(self._tuning_goal_pi_index) == 0:
            # No match
            raise ValueError('No PI name matches tuning_goal_regex ' + tuning_goal_names)

    def get_tuning_goal(self, pis):
        # type: (List[float]) -> float
        # Make sure the PIs are of the right dimension
        assert len(pis) == len(self._pi_names)
        result = 0
        for i in self._tuning_goal_pi_index:
            result += pis[i]
        result = result / len(self._tuning_goal_pi_index)
        assert -1 <= result <= 1
        return result


class MockTuningGoalCalculator(TuningGoalCalculatorBase):
    """This mock calculator always returns the first element of PI as reward

    It is mainly used in test cases."""
    def __init__(self, logger=None, config=None, pi_names=None, tuning_goal_names=None):
        # type: (logging.Logger, ConfigBase, List[str], str) -> None
        super(MockTuningGoalCalculator, self).__init__(logger, config, pi_names, tuning_goal_names)

    def get_tuning_goal(self, pis):
        # type: (List[float]) -> float
        # Make sure the PIs are of the right dimension
        return pis[0]
