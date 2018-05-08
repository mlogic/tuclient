"""ProtocolExtensionBase class"""
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
from typing import Any, List

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import abc
import logging
from uuid import UUID


class ProtocolExtensionBase(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, logger, client_id):
        # type: (logging.Logger, UUID) -> None
        self._logger = logger
        self._client_id = client_id

    def __del__(self):
        self.disconnect()

    @abc.abstractmethod
    def connect_to_gateway(self):
        """Establish a connection

        Call this method before sending or receiving anything."""
        pass

    @property
    @abc.abstractmethod
    def connected(self):
        # type: () -> bool
        """Check if a connection has been established"""
        pass

    @abc.abstractmethod
    def disconnect(self):
        """Close a connection

        Call this method if you need to manually close a connection. It will be called
        automatically upon exit. This method should be idempotent."""
        pass

    @abc.abstractmethod
    def receive(self, timeout):
        # type: (int) -> List[Any]
        """Block until data arrives
        :param timeout: timeout in how many ms"""
        pass

    @abc.abstractmethod
    def send_list(self, data):
        # type: (List[Any]) -> None
        """Send a list of floats
        :param data : a list of floats"""
        pass
