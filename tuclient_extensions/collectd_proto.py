"""Parser for the collectd network protocol

Implements parsing incoming collectd parts according to
https://collectd.org/wiki/index.php/Binary_protocol
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

import struct

header_struct = struct.Struct("!2H")
short_struct = struct.Struct("!H")
ulonglong_struct = struct.Struct("!Q")
double_struct = struct.Struct("<d")

# Part types
PART_TYPE_HOST = 0
PART_TYPE_TIME = 1
PART_TYPE_PLUGIN = 2
PART_TYPE_PLUGIN_INSTANCE = 3
PART_TYPE_TYPE = 4
PART_TYPE_TYPE_INSTANCE = 5
PART_TYPE_VALUES = 6
PART_TYPE_INTERVAL = 7
PART_TYPE_TIME_HR = 8
PART_TYPE_INTERVAL_HR = 9

# Data types
DATA_TYPE_COUNTER = 0
DATA_TYPE_GAUGE = 1
DATA_TYPE_DERIVE = 2
DATA_TYPE_ABSOLUTE = 3


def parse_values(buf, start, part_len):
    num_values = short_struct.unpack_from(buf, start + header_struct.size)[0]
    if part_len != header_struct.size + short_struct.size + num_values * (1 + 8):
        raise ValueError('Corrupted part received')

    result = []
    data_type_offset = start + header_struct.size + short_struct.size
    value_offset = data_type_offset + num_values
    for i in range(num_values):
        data_type = buf[data_type_offset + i]
        if data_type == DATA_TYPE_COUNTER:
            val = ulonglong_struct.unpack_from(buf, value_offset + i * 8)[0]
        elif data_type == DATA_TYPE_GAUGE:
            val = double_struct.unpack_from(buf, value_offset + i * 8)[0]
        elif data_type == DATA_TYPE_DERIVE:
            val = ulonglong_struct.unpack_from(buf, value_offset + i * 8)[0]
        elif data_type == DATA_TYPE_ABSOLUTE:
            val = ulonglong_struct.unpack_from(buf, value_offset + i * 8)[0]
        else:
            raise ValueError('Unknown data type {type}'.format(type=data_type))
        result.append((data_type, val))

    return result


def parse_number(buf, start, part_len):
    assert part_len == 12
    return ulonglong_struct.unpack_from(buf, start + header_struct.size)[0]


def parse_time_hr(buf, start, part_len):
    # High resolution time is stored in the unit of 1<<30. We convert it to a float.
    return parse_number(buf, start, part_len) / (1 << 30)


def parse_string(buf, start, part_len):
    # -1 to remove the NULL at end of buf
    return buf[start + header_struct.size:start + part_len - 1].decode('ascii')


part_parsers = {
    PART_TYPE_VALUES: parse_values,
    PART_TYPE_TIME: parse_number,
    PART_TYPE_TIME_HR: parse_time_hr,
    PART_TYPE_INTERVAL: parse_number,
    PART_TYPE_INTERVAL_HR: parse_number,
    PART_TYPE_HOST: parse_string,
    PART_TYPE_PLUGIN: parse_string,
    PART_TYPE_PLUGIN_INSTANCE: parse_string,
    PART_TYPE_TYPE: parse_string,
    PART_TYPE_TYPE_INSTANCE: parse_string
}


def parse_parts(buf):
    """Parse buf into a list of parts"""
    parts = []
    start = 0
    end = len(buf)
    if end <= 4:
        raise ValueError('Corrupted part received: ' + buf)
    while start < end:
        part_type, part_len = header_struct.unpack_from(buf, start)
        if part_len > end - start:
            # Current buf no longer has a whole part. Remove the parsed part and return.
            return parts, buf[start:]
        elif part_type not in part_parsers:
            raise ValueError('Received unknown part type: {part_type}'.format(part_type=part_type))
        else:
            parts.append((part_type, part_parsers[part_type](buf, start, part_len)))
            start += part_len
    return parts, b''
