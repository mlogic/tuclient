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

# Python 2.7 doesn't have JSONDecodeError; it uses ValueError instead
try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError
# Python 2.7 doesn't have time.monotonic().
import time
try:
    monotonic_time = time.monotonic
except AttributeError:
    # Use the monotonic module instead.
    import monotonic
    monotonic_time = monotonic.monotonic


from enum import Enum
class ClusterStatus(Enum):
    OFFLINE = 0
    ALL_OK = 1
    NOT_SETUP = 2      # This cluster hasn't been set up yet (desired cluster info not set).
    NODES_MISMATCH = 3
    NODES_LOST = 4

class ClientStatus(Enum):
    OFFLINE = 0
    ALL_OK = 1
    NOT_SETUP = 2
    HANDSHAKE1_AUTHENTICATING = 3
    HANDSHAKE2_UPLOAD_METADATA = 4
    CONNECTION_ERROR = 5
    GETTER_ERROR = 6
    SETTER_ERROR = 7

ClientStatusToStrMapping = {
    ClientStatus.OFFLINE: 'Offline',
    ClientStatus.ALL_OK: 'Running',
    ClientStatus.NOT_SETUP: 'Not setup',
    ClientStatus.HANDSHAKE1_AUTHENTICATING: 'Authenticating',
    ClientStatus.HANDSHAKE2_UPLOAD_METADATA: 'Syncing metadata',
    ClientStatus.CONNECTION_ERROR: 'Connection error',
    ClientStatus.GETTER_ERROR: 'Getter error',
    ClientStatus.SETTER_ERROR: 'Setter error',
}


# Enum is not JSON serializable. IntEnum is, but in Python 3 only. So we write
# our own Enum JSON Encoder and decoder.
import json
class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if issubclass(type(obj), Enum):
            return {"__enum__": str(obj)}
        return json.JSONEncoder.default(self, obj)
def as_enum(d):
    if "__enum__" in d:
        name, member = d["__enum__"].split(".")
        return getattr(globals()[name], member)
    else:
        return d


def overrides(interface_class):
    def overrider(method):
        assert (method.__name__ in dir(interface_class))
        return method

    return overrider
