"""Common routines of TuneUp.ai Client
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

# Enum is not JSON serializable. IntEnum is.
from enum import IntEnum
# Python 2.7 doesn't have time.monotonic().
import time
try:
    monotonic_time = time.monotonic
except AttributeError:
    # Use the monotonic module instead.
    import monotonic
    monotonic_time = monotonic.monotonic


class ClusterStatus(IntEnum):
    OFFLINE = 0
    ALL_OK = 1
    NOT_SETUP = 2      # This cluster hasn't been set up yet (desired cluster info not set).
    NODES_MISMATCH = 3
    NODES_LOST = 4


class ClientStatus(IntEnum):
    OFFLINE = 0
    ALL_OK = 1
    NOT_SETUP = 2
    HANDSHAKE1_AUTHENTICATING = 3
    HANDSHAKE2_UPLOAD_METADATA = 4
    CONNECTION_ERROR = 5
    GETTER_ERROR = 6
    SETTER_ERROR = 7


def overrides(interface_class):
    def overrider(method):
        assert (method.__name__ in dir(interface_class))
        return method

    return overrider
