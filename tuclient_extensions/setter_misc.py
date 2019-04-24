"""Functions for calculation parameter values"""
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


import os
import sys
from typing import List


def get_proc_cmdline(pid):
    # type (int) -> str
    """Get the cmdline of a process by pid"""
    with open('/proc/{}/cmdline'.format(pid), mode='rb') as fd:
        return fd.read().decode().split('\x00')[0]


def get_pids(name):
    # type (str) -> List[int]
    """Get the pids by process names"""
    result = []
    for dirname in os.listdir('/proc'):
        if dirname == 'curproc':
            continue

        try:
            # First test if the dirname is an integer number. Skip if it isn't.
            pid = int(dirname)
            with open('/proc/{}/cmdline'.format(dirname), mode='rb') as fd:
                proc_cmdline = fd.read().decode().split('\x00')[0]
        except Exception:
            continue

        if name in proc_cmdline:
            result.append(pid)

    return result


def param_value_from_range(a, b, action_value):
    # type: (float, float, float) -> str
    """Convert a float in [-1, 1] to a parameter value"""
    assert a <= b
    return str(int((b - a) / 2 * (action_value + 1) + a))
