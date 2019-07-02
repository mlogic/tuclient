"""Collects operating system information using collectd"""
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

from tuclient import *
import tuclient_extensions.collectd_ext
from tuclient_extensions import collectd_proto
from typing import List


class Getter(GetterExtensionBase):
    """Getter and Setter for using collectd to collect operating system information"""

    def __init__(self, logger, host, config=None, collectd_instance=None):
        """Create a CollectdOS instance

        :param logger: logger
        :param config: a ConfigBase instance for accessing configuration options
        :param collectd_instance: a collectd_ext instance"""
        super(Getter, self).__init__(logger, host, config, 'collectd_os')
        if collectd_instance is None:
            self._collectd = tuclient_extensions.collectd_ext.get_collectd_ext_instance(logger)
        else:
            self._collectd = collectd_instance
        self._collectd.add_plugin('cpu')
        self._collectd.register_callback('cpu', self._on_receiving_cpu_data)

        self._last_cpu_jiffies = None
        self._last_cpu_jiffies_time = None
        self._current_cpu_jiffies = dict()
        self._current_cpu_jiffies_num_of_values = 0
        # last_cpu_jiffies_diff stores the differences of jiffies between two collection periods
        self._last_cpu_jiffies_diff = None
        self._num_cpu = None
        self._num_cpu_type_instances = None

    def _on_receiving_cpu_data(self, host, plugin, parts):
        assert plugin == 'cpu'
        plugin_instance = None
        ts = None
        type = None
        type_instance = None
        # Number of values collected for the current period

        self._logger.debug('Received CPU parts: ' + str(parts))

        for part_type, part_data in parts:
            if part_type == tuclient_extensions.collectd_proto.PART_TYPE_TIME_HR:
                assert isinstance(part_data, float)
                ts = part_data
            elif part_type == collectd_proto.PART_TYPE_PLUGIN_INSTANCE:
                assert isinstance(part_data, str)
                plugin_instance = int(part_data)
            elif part_type == collectd_proto.PART_TYPE_TYPE:
                assert isinstance(part_data, str)
                type = part_data
            elif part_type == collectd_proto.PART_TYPE_TYPE_INSTANCE:
                assert isinstance(part_data, str)
                type_instance = part_data
            elif part_type == collectd_proto.PART_TYPE_VALUES:
                assert len(part_data) == 1
                assert part_data[0][0] == collectd_proto.DATA_TYPE_DERIVE
                assert isinstance(part_data[0][1], int)

                # Check if this is the first time we have received full data for one collection period/
                # We used to do this up in the section where we process PART_TYPE_TIME_HR, but sometimes
                # we receive a trailing PART_TYPE_TIME_HR without data, which could disrupt the detection
                # of time gap, so we do it here. See test_parsing_data_bug_2() for a test sample. Now
                # we only consider a PART_TYPE_TIME_HR part to be valid when it is followed by a VALUE
                # part.
                if self._last_cpu_jiffies_time is not None and ts - self._last_cpu_jiffies_time > 0.9:
                    # Next collection period has began
                    if self._last_cpu_jiffies is None:
                        # Check if all CPUs have the same number of type instances
                        # next(iter()) should be faster than list()[0]
                        self._num_cpu_type_instances = len(next(iter(self._current_cpu_jiffies.values())))
                        for _, v in self._current_cpu_jiffies.items():
                            if self._num_cpu_type_instances != len(v):
                                # This could happen when what we receive is only the ending parts of
                                # the first second. We should just ignore it.
                                self._logger.debug('Received incomplete data for second {}, ignoring them.'.format(
                                    self._last_cpu_jiffies_time
                                ))
                                self._num_cpu_type_instances = None
                                break
                        if self._num_cpu_type_instances is not None:
                            self._logger.debug('Finished receiving CPU jiffies of the first collection period')
                            self._num_cpu = len(self._current_cpu_jiffies)
                            self._logger.debug('Number of CPU: {}'.format(self._num_cpu))
                            self._logger.debug('Number of CPU type instances: {}'.format(self._num_cpu_type_instances))
                            self._last_cpu_jiffies = self._current_cpu_jiffies
                        self._current_cpu_jiffies = dict()
                        self._current_cpu_jiffies_num_of_values = 0
                    else:
                        # _current_cpu_jiffies should have already been processed
                        assert len(self._current_cpu_jiffies) == 0
                self._last_cpu_jiffies_time = ts


                cpu_id = int(plugin_instance)
                if cpu_id not in self._current_cpu_jiffies:
                    self._current_cpu_jiffies[cpu_id] = dict()
                # Data of the same type_instance shouldn't be received twice
                if type_instance in self._current_cpu_jiffies[cpu_id]:
                    err_msg = 'Warning: type instance "{type_instance}" appeared twice for CPU {cpu_id} at time {ts}'\
                        .format(type_instance=type_instance, cpu_id=cpu_id, ts=ts)
                    self._logger.warning(err_msg)
                    self._logger.warning('Received parts: ' + str(parts))
                    # Don't raise error because this could happen every few hours for unknown reasons.
                    # raise ValueError(err_msg)
                self._current_cpu_jiffies[cpu_id][type_instance] = part_data[0][1]
                self._current_cpu_jiffies_num_of_values += 1
                if self._last_cpu_jiffies is not None and self._current_cpu_jiffies_num_of_values == \
                        self._num_cpu * self._num_cpu_type_instances:
                    # We've received all CPU values for this period. Calculate diffs between
                    # current jiffies and previous jiffies.
                    self._logger.debug('Finished receiving all values for current CPU jiffies')
                    self._logger.debug('current_cpu_jiffies: {current_cpu_jiffies}'.format(
                        current_cpu_jiffies=self._current_cpu_jiffies))
                    jiffies_diff = dict()
                    for _cpu_id in self._last_cpu_jiffies:
                        jiffies_diff[_cpu_id] = dict()
                        for _type_instance in self._last_cpu_jiffies[_cpu_id]:
                            jiffies_diff[_cpu_id][_type_instance] = self._current_cpu_jiffies[_cpu_id][_type_instance] - \
                                                                    self._last_cpu_jiffies[_cpu_id][_type_instance]
                    self._last_cpu_jiffies = self._current_cpu_jiffies
                    self._current_cpu_jiffies = dict()
                    self._current_cpu_jiffies_num_of_values = 0
                    # For thread-safety, we write to self._last_cpu_jiffies_diff last, which is being
                    # monitored by collect() from another thread.
                    self._last_cpu_jiffies_diff = jiffies_diff

    @overrides(GetterExtensionBase)
    def start(self):
        self._collectd.start()

    @overrides(GetterExtensionBase)
    def collect(self):
        # type: () -> List[float]
        """Collect Performance Indicators"""
        start_ts = monotonic_time()
        while self._last_cpu_jiffies_diff is None:
            if not self._collectd.is_alive():
                raise RuntimeError('collectd thread is dead')
            time.sleep(0.01)
            if monotonic_time() - start_ts > 20:
                err_msg = 'collectd_os.collect() timed out. Please check collectd log for error information'
                self._logger.error(err_msg)
                raise RuntimeError(err_msg)

        # Make a copy because self._last_cpu_jiffies_diff could change anytime. No need to
        # use deepcopy, because self._last_cpu_jiffies_diff will only be changed to point
        # to another dict, not being modified in any other way.
        last_cpu_jiffies_diff = self._last_cpu_jiffies_diff
        # It is ok if self._last_cpu_jiffies_diff is changed after last statement and before
        # we write None to it, because that would be rare and would only cause us to
        # lost 1 second's data.
        self._last_cpu_jiffies_diff = None

        # We have data from all plugins. Prepare to send them out.
        outgoing_values = [0] * self._num_cpu * self._num_cpu_type_instances
        i = 0
        for cpu_id in sorted(last_cpu_jiffies_diff.keys()):
            half_total_jiffies = sum(last_cpu_jiffies_diff[cpu_id].values()) / 2
            for type_instance in sorted(last_cpu_jiffies_diff[cpu_id].keys()):
                # Normalize to [-1, 1]
                outgoing_values[i] = last_cpu_jiffies_diff[cpu_id][type_instance] / half_total_jiffies - 1
                i += 1

        return outgoing_values

    @property
    @overrides(GetterExtensionBase)
    def pi_names(self):
        # type: () -> List[str]
        """Return the list of all Performance Indicator names"""
        while self._last_cpu_jiffies is None:
            if not self._collectd.is_alive():
                raise RuntimeError('collectd thread is dead')
            time.sleep(0.01)
        pis = []
        for cpu_id in sorted(self._last_cpu_jiffies.keys()):
            for type_instance in sorted(self._last_cpu_jiffies[cpu_id].keys()):
                pis.append('{host}/cpu/{cpu_id}/{type_instance}'.format(
                    host=self._host, cpu_id=cpu_id, type_instance=type_instance
                ))
        return pis

    @overrides(SetterExtensionBase)
    def action(self, actions):
        # type: (List[float]) -> None
        """Perform actions
        :param actions: a list of actions to perform"""
        pass

    @property
    @overrides(SetterExtensionBase)
    def parameter_names(self):
        # type: () -> List[str]
        """Return the list of all parameters"""
        return []

    def stop(self):
        if self._collectd is not None:
            self._collectd.stop()
