"""Common getters"""
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

import functools
import importlib
from .getter_setter_misc import *
import re
import signal
from tuclient import *
# typing.NamedTuple is better than collections.namedtuple because the former allows
# setting the types of fields.
from typing import Callable, Dict, List, NamedTuple, Set


# We can't use the following better format because we need to support Python 2
#    name: str
#    calc_param_value_func: Callable
# calc_param_value_func is a callable for calculating the actual parameter value
# from the float value between -1 and 1 that we receive from the engine.
PIInfo = NamedTuple('PIInfo', [('full_name', str),
                               ('input_file', str),
                               ('field', int),
                               ('normalization_func', Callable)])


class Getter(GetterExtensionBase):
    """Common getters"""

    @staticmethod
    def raise_interruptederror(signum, _):
        if signum == signal.SIGALRM:
            raise InterruptedError

    def __init__(self, logger, host, config=None, name='common_setters'):
        """Create a Common Getter instance

        :param logger: logger
        :param host: host name
        :param config: a ConfigBase instance for accessing configuration options
        :param name: name of the getter
        """
        super(Getter, self).__init__(logger, host, config, name)

        # Install our SIGALRM handler that raises an InterruptedError so that
        # our blocking read() could timeout.
        signal.signal(signal.SIGALRM, self.raise_interruptederror)

        # Load settings for the common getters from config. PIs are ground by their
        # intervals.
        pi_names = [x.strip() for x in config.get_config()['common_getters_params'].split(',')]
        # Sort PIs by names so that PI data are comparable as long as user
        # supplies the same PIs regardless of their order.
        pi_names.sort()
        # PIs are grouped by interval
        self._PIs = dict()                      # type: Dict[int, List[PIInfo]]
        # Input file names grouped by interval
        self._input_file_names = dict()         # type: Dict[int, Set[str]]
        self._input_file_objects = dict()       # type: Dict[str, object]
        # The last received line of data for each input file. They will be used
        # when the timestamp from the input file doesn't match 100% with
        # the required_time, such as when required_time is 4, but we only have
        # data of time, 3, 5, etc. In that case, we return data of time 3
        # when data of time 5 is received and we could be sure that we wouldn't
        # receive data of time 4.
        self._input_file_lastest_data = dict()  # type: Dict[str, Optional[List[Any]]]
        self._PI_names = list()

        for name in pi_names:
            interval = int(config.get_config()[name + '_interval'])
            if interval not in self._PIs:
                self._PIs[interval] = []
                self._input_file_names[interval] = set()
            if name + '_input_file' in config.get_config():
                input_file = config.get_config()[name + '_input_file']
                self._input_file_names[interval].add(input_file)
                input_field = int(config.get_config()[name + '_field'])

                pi_full_name = host + '/' + name
                range_str = config.get_config()[name + '_range']
                m = re.match(r"\[(\d+)[, ]*(\d+)\]", range_str)
                if m is not None:
                    # m.group(0) is the entire match, so what we need are group(1) and group(2)
                    normalization_func = functools.partial(normalize_from_range, float(m.group(1)),
                                                           float(m.group(2)))
                    pi_type = 'range'
                    self._PIs[interval].append(PIInfo(pi_full_name,
                                                      input_file,
                                                      input_field,
                                                      normalization_func))
                    self._PI_names.append(pi_full_name)
                else:
                    pi_type = 'categorical'
                    raise ValueError('Reading categorical PIs is not supported yet')
                logger.info('Loaded {type} PI: name {pi_full_name}, collect interval {interval}, '
                            'input_file {input_file}, range {range_str}'.format(
                                type=pi_type, pi_full_name=pi_full_name, interval=interval,
                                input_file=input_file, range_str=range_str))
            else:
                raise ValueError("Common getter {name} doesn't have input file name.")

    @overrides(GetterExtensionBase)
    def start(self):
        pass

    @overrides(GetterExtensionBase)
    def collect(self, interval, required_time):
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
        if interval == -1:
            # TODO: This shouldn't be needed when TUE-224 is finished.
            assert len(self._PIs) == 1
            interval = list(self._PIs.keys())[0]

        # Required data line of each input file
        required_data_lines = dict()   # type: Dict[str, List[Any]]
        # Read in data lines of all input files
        for file_name in self._input_file_names[interval]:
            # Check if previously read data already matches the required_time
            prev_columns = self._input_file_lastest_data.get(file_name, None)
            if prev_columns is not None:
                ts = prev_columns[0]
                if ts >= required_time:
                    required_data_lines[file_name] = prev_columns
                    del self._input_file_lastest_data[file_name]
                    continue

            # Previously read data doesn't meet the required_time. Read in more data.
            # Open file object if necessary.
            if file_name not in self._input_file_objects:
                try:
                    # open() defaults to blocking I/O. Open the fifo in rw mode
                    # so we never have to worry about receiving EOF. This is important
                    # because, if the writer closes and opens the fifo frequently,
                    # there could be a race condition where we (the reader) close
                    # a fd after receiving an EOF after the writer has already opened
                    # again. In that case, the writer would fail with a BrokenPipeError.2
                    #
                    # There's no way to open a stream for read/write in text mode
                    # (see https://bugs.python.org/issue20074), so we have to use
                    # binary mode without buffering.
                    fobj = open(file_name, 'r+b', buffering=0)
                except (IOError, OSError) as err:
                    self._logger.warning('Cannot open {file_name} to read: {err}'.format(file_name=file_name,
                                                                                         err=str(err)))
                    return []
                self._input_file_objects[file_name] = fobj
            else:
                fobj = self._input_file_objects[file_name]

            while True:

                # Read data.
                try:
                    try:
                        signal.alarm(interval)
                        line = fobj.readline().decode('ascii')
                    finally:
                        # Make sure we remove the alarm within the try..except wrapping.
                        signal.alarm(0)
                except InterruptedError:
                    # Timeout, return an empty list
                    self._logger.warning('Timeout reading from ' + file_name)
                    # TODO: maybe we can return the data in self._input_file_latest_data
                    return []

                line = line.rstrip('\r\n')

                self._logger.debug('From {file_name} read line {data}'.format(
                    file_name=file_name, data=line))
                columns = line.split(',')        # type: List[Any]
                # first column is timestamp
                ts = int(columns[0])
                columns[0] = ts
                if ts < required_time:
                    self._input_file_lastest_data[file_name] = columns
                elif ts == required_time:
                    # Remove the obsoleted saved data to prevent them from being
                    # used.
                    self._input_file_lastest_data[file_name] = None
                    required_data_lines[file_name] = columns
                    # Stop reading when we find what we want
                    break
                else:
                    # ts > required_time
                    if self._input_file_lastest_data.get(file_name, None) is None:
                        # We don't have any data from time before the required_time, return
                        # nothing.
                        self._input_file_lastest_data[file_name] = columns
                        return []
                    required_data_lines[file_name] = self._input_file_lastest_data[file_name]
                    self._input_file_lastest_data[file_name] = columns
                    break

        result = []
        for pi in self._PIs[interval]:
            raw_value = float(required_data_lines[pi.input_file][pi.field])
            pi_value = pi.normalization_func(raw_value)
            if pi_value < -1 or pi_value > 1:
                self._logger.warning('Common getter collectd {pi_name} raw value {raw_value} that is outside the '
                                     'normalization range. Please change the range accordingly.'.format(
                                         pi_name=pi.full_name, raw_value=raw_value))
            result.append(clip(pi_value, -1, 1))

        return result

    @property
    @overrides(GetterExtensionBase)
    def pi_names(self):
        # type: () -> List[str]
        """Return the list of all parameters"""
        return self._PI_names

    def stop(self):
        for _, fh in self._input_file_objects.items():
            fh.close()
