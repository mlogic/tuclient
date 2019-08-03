"""Collects NGINX information using collectd"""
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

from collections import OrderedDict
from tuclient import *
import tuclient_extensions.collectd_ext
from tuclient_extensions import collectd_proto
from typing import Dict, List


class Getter(GetterExtensionBase):
    """Getter and Setter for using collectd to collect operating system information"""

    # Make sure the dict keeps its order
    EXPECTED_DATA_TYPES = OrderedDict({
        'connections_accepted': (collectd_proto.DATA_TYPE_DERIVE, '_connection_normalize_factor'),
        'connections_failed': (collectd_proto.DATA_TYPE_DERIVE, '_connection_normalize_factor'),
        'connections_handled': (collectd_proto.DATA_TYPE_DERIVE, '_connection_normalize_factor'),
        'nginx_connections_active': (collectd_proto.DATA_TYPE_GAUGE, '_connection_normalize_factor'),
        'nginx_connections_reading': (collectd_proto.DATA_TYPE_GAUGE, '_connection_normalize_factor'),
        'nginx_connections_waiting': (collectd_proto.DATA_TYPE_GAUGE, '_connection_normalize_factor'),
        'nginx_connections_writing': (collectd_proto.DATA_TYPE_GAUGE, '_connection_normalize_factor'),
        'nginx_requests': (collectd_proto.DATA_TYPE_DERIVE, '_request_normalize_factor'),
    })

    def __init__(self, logger, host, config=None, collectd_instance=None):
        """Create a CollectdOS instance

        :param logger: logger
        :param config: a ConfigBase instance for accessing configuration options
        :param collectd_instance: a collectd_ext instance"""
        super(Getter, self).__init__(logger, host, config, 'collectd_nginx')
        if collectd_instance is None:
            self._collectd = tuclient_extensions.collectd_ext.get_collectd_ext_instance(logger)
        else:
            self._collectd = collectd_instance

        # Default options
        plugin_options = None
        self._connection_normalize_factor = 1000 / 2
        self._request_normalize_factor = 10000 / 2
        if config is not None:
            self._connection_normalize_factor = int(config.get_config().get('collectd_nginx_max_connections',
                                                                            self._connection_normalize_factor * 2)) / 2
            self._request_normalize_factor = int(config.get_config().get('collectd_nginx_max_requests',
                                                                         self._request_normalize_factor * 2)) / 2
            if 'collectd_nginx_status_url' in config.get_config():
                plugin_options = f'URL "{config.get_config()["collectd_nginx_status_url"]}"'
            else:
                err_msg = 'collectd_nginx_status_url is missing'
                logger.error(err_msg)
                raise ValueError(err_msg)
        self._collectd.add_plugin('nginx', options=plugin_options)
        self._collectd.register_callback('nginx', self._on_receiving_nginx_data)

        # raw data is before we calculate the diff between those derived data
        self._last_pi_raw_data = None   # type: Dict
        self._last_pi_data_ts = None    # type: float
        self._current_pi_raw_data = dict()
        # the processed PI data
        self._pi_data = None

    def _on_receiving_nginx_data(self, host, plugin, parts):
        assert plugin == 'nginx'
        # Packets are separated by the Host part.
        # plugin_instance is either not used or just empty for NGINX plugin
        # plugin_instance = None
        ts = None
        type = None
        type_instance = None
        # Number of values collected for the current period

        self._logger.debug('Received NGINX parts: ' + str(parts))

        for part_type, part_data in parts:
            if part_type == tuclient_extensions.collectd_proto.PART_TYPE_TIME_HR:
                assert isinstance(part_data, float)
                ts = part_data
            elif part_type == collectd_proto.PART_TYPE_PLUGIN_INSTANCE:
                # plugin_instance is either not used or just empty for NGINX plugin
                pass
            elif part_type == collectd_proto.PART_TYPE_TYPE:
                assert isinstance(part_data, str)
                type = part_data
            elif part_type == collectd_proto.PART_TYPE_TYPE_INSTANCE:
                assert isinstance(part_data, str)
                type_instance = part_data
            elif part_type == collectd_proto.PART_TYPE_VALUES:
                assert len(part_data) == 1

                # We used to do this up in the section where we process PART_TYPE_TIME_HR, but sometimes
                # we receive a trailing PART_TYPE_TIME_HR without data, which could disrupt the detection
                # of time gap, so we do it here. See test_collectd_nginx.test_parsing_data_bug_0() for a
                # test sample. Now we only consider a PART_TYPE_TIME_HR part to be valid when it is
                # followed by a VALUE part.
                if self._last_pi_data_ts is not None and ts - self._last_pi_data_ts > 0.9:
                    # Next collection period has began
                    # self._current_pi_raw_data should have already been processed
                    assert len(self._current_pi_raw_data) == 0
                self._last_pi_data_ts = ts

                if type_instance is None or type_instance == '':
                    data_name = type
                else:
                    data_name = '{type}_{type_instance}'.format(type=type, type_instance=type_instance)
                assert part_data[0][0] == Getter.EXPECTED_DATA_TYPES[data_name][0]
                self._current_pi_raw_data[data_name] = part_data[0][1]
                if len(self._current_pi_raw_data) == 8:
                    if self._last_pi_raw_data is not None:
                        pi_data = dict()
                        for data_name, data_type in Getter.EXPECTED_DATA_TYPES.items():
                            if data_type[0] == collectd_proto.DATA_TYPE_DERIVE:
                                pi_data[data_name] = self._current_pi_raw_data[data_name] - \
                                                     self._last_pi_raw_data[data_name]
                            else:
                                pi_data[data_name] = self._current_pi_raw_data[data_name]
                        # Ready it for collection after it is all finished. self._pi_data
                        # must be modified atomically because there's no lock to protect it.
                        self._pi_data = pi_data
                        self._logger.debug('Finished receiving all NGINX values for current tick')
                    self._last_pi_raw_data = self._current_pi_raw_data
                    self._current_pi_raw_data = dict()

    @overrides(GetterExtensionBase)
    def start(self):
        self._collectd.start()

    @overrides(GetterExtensionBase)
    def collect(self, _interval=-1, _required_time=-1):
        # type: (int, int) -> List[float]
        """Collect Performance Indicators"""
        start_ts = monotonic_time()
        while self._pi_data is None:
            if not self._collectd.is_alive():
                raise RuntimeError('collectd thread is dead')
            time.sleep(0.01)
            # It could take a long time to read status information from a busy NGINX server.
            # We've observed as long as 14 seconds.
            if monotonic_time() - start_ts > 60:
                err_msg = 'Reading data from NGINX timed out. Please check collectd log for error information'
                self._logger.error(err_msg)
                raise RuntimeError(err_msg)

        # Make a copy because self._pi_data could change anytime. No need to
        # use deepcopy, because self._pi_data will only be changed to point
        # to another dict, not being modified in any other way.
        pi_data = self._pi_data
        # It is ok if self._pi_data is changed after last statement and before
        # we write None to it, because that would be rare and would only cause us to
        # lost 1 second's data.
        self._pi_data = None
        outgoing_values = [0] * len(Getter.EXPECTED_DATA_TYPES)
        i = 0
        for name, data_type in Getter.EXPECTED_DATA_TYPES.items():
            normalizer = self.__dict__[data_type[1]]
            outgoing_values[i] = clip(pi_data[name] / normalizer - 1, -1, 1)
            if pi_data[name] > normalizer * 2:
                err_msg = 'Collected {name}: {value} is larger than its normalize factor '\
                          'and is normalized to {outgoing_value}. Increase its normalize factor!'.format(
                              name=name, value=pi_data[name], outgoing_value=outgoing_values[i])
                self._logger.warning(err_msg)
            else:
                self._logger.debug('Collected {name}: {value}, normalized to {outgoing_value}'.format(
                    name=name, value=pi_data[name], outgoing_value=outgoing_values[i]))
            i += 1
        return outgoing_values

    @property
    @overrides(GetterExtensionBase)
    def pi_names(self):
        # type: () -> List[str]
        """Return the list of all Performance Indicator names"""
        return [f'{self._host}/nginx/{x}' for x in Getter.EXPECTED_DATA_TYPES.keys()]

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
