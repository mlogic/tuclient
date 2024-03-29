"""GetterExtensionBase class"""
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


class GetterExtensionBase(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, logger, host, config, name=''):
        # type: (logging.Logger, str, Optional[ConfigBase], str) -> None
        self._logger = logger
        self._host = host
        self._config = config
        self.name = name

    @abc.abstractmethod
    def start(self):
        """Notify the getter that initialization is done and collection will start soon"""
        pass

    @abc.abstractmethod
    def collect(self, interval=-1, required_time=-1):
        # type: (int, int) -> List[float]
        """Collect Performance Indicators

        Collect all PIs that have the desired collection interval for the specified
        required_time.

        For test cases, if all parameters have the same interval, we can set interval
        to -1 and the actions will be applied to all parameters. The behavior is
        undefined if the parameters have more than one interval.

        :param interval: intervals for this batch of actions
        :param required_time: the required time of data
        """
        pass

    @property
    @abc.abstractmethod
    def pi_names(self):
        # type: () -> List[str]
        """Return the list of all Performance Indicator names"""
        pass

    @abc.abstractmethod
    def stop(self):
        """Notify the getter that tuclient is shutting done"""
        pass
