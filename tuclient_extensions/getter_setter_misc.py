"""Misc. functions used by all getters and setters"""
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
from typing import List, Set


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


def normalize_from_range(a, b, n):
    # type: (float, float, float) -> float
    """Normalize n (in range (a,b)) to [-1,1]"""
    return (n - a) / ((b - a) / 2) - 1


def param_value_from_range(a, b, n, action_values):
    # type: (float, float, int, List[float]) -> str
    """Convert a float action_values[n] (within [-1, 1]) to a parameter value"""
    assert a <= b
    return str(int((b - a) / 2 * (action_values[n] + 1) + a))


def param_value_from_set(param_categories, n, action_values):
    # type: (List[str], int, List[float]) -> str
    """Pick a value from the set according to the action value

    We use a 1-of-k encoding for categorical (discrete) parameter values. For example,
    we have a parameter called 'pick_a_day" and the candidate values are
    (sun, mon, tue, wed). param_value_from_set() is called four times with
    the following arguments:
    param_value_from_set(set, 'pick_a_day', 0, [0.1, 0.2, 0.3, -0.1])

    Then the third value from the set, 'tue', will be picked.
    """
    assert n + len(param_categories) <= len(action_values)

    # Extract the action values that are related to our group
    group_action_values = action_values[n:n+len(param_categories)]
    # Use the simple method of max() and index() to find the location
    # of the action that has the max value. For small lists (people
    # usually have around 4 to 5 candidate values for one parameter),
    # this is faster than np.argmax() and max(enumerate()). See
    # https://stackoverflow.com/questions/6193498/pythonic-way-to-find-maximum-value-and-its-index-in-a-list
    max_val = max(group_action_values)
    max_idx = group_action_values.index(max_val)

    return param_categories[max_idx]
