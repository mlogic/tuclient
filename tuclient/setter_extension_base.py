"""SetterExtensionBase class"""
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
from typing import List

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import abc
from .configbase import ConfigBase
import logging


class SetterExtensionBase(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, logger, config):
        # type: (logging.Logger, ConfigBase) -> None
        self._logger = logger
        self._config = config

    @abc.abstractmethod
    def action(self, actions):
        # type: (List[float]) -> None
        """Perform actions
        :param actions: a list of actions to perform"""
        pass
