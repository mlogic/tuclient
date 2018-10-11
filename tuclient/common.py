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

import sys
import subprocess

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

class ClusterStatus(Enum):
    OFFLINE = 30
    TUNING_TARGET_REACHED = 31
    NOT_SETUP = 32
    TUNING_TARGET_NOT_REACHED = 33
    CLIENT_CONNECTION_ERROR = 34
    CLIENT_ERROR = 35
    INTERNAL_ERROR = 36

ClusterStatusToStrMapping = {
    ClusterStatus.OFFLINE: 'Offline',
    ClusterStatus.TUNING_TARGET_REACHED: 'Tuning; training finished',
    ClusterStatus.NOT_SETUP: 'Not setup',
    ClusterStatus.TUNING_TARGET_NOT_REACHED: 'Tuning; training not finished',
    ClusterStatus.CLIENT_CONNECTION_ERROR: 'Cannot connect to all clients',
    ClusterStatus.CLIENT_ERROR: 'One or more client error',
    ClusterStatus.INTERNAL_ERROR: 'Internal error; contact support'
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


def run_shell_command(cmd):
    # type: (str) -> str
    """Run a shell command and return its stdout"""
    # subprocess.run() is not available in Python 2.7
    if sys.version_info[0] >= 3:
        cp = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        cp_str = cp.stdout.decode('utf-8')
    else:
        # The following ugly code is only needed for Python 2
        cp = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        cp_str = ''
        while cp.poll() is None:
            cp_str += cp.stdout.read()
        cp_str += cp.communicate()[0]

    return_code = cp.returncode
    if return_code != 0:
        err_msg = 'Subprocess {cmd} returned error code {rc} and output: {cp_str}'.format(cmd=cmd, rc=return_code,
                                                                                          cp_str=cp_str)
        raise RuntimeError(err_msg)

    return cp_str
