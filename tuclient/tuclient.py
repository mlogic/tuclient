#!/usr/bin/env python
"""TuneUp.ai Client"""
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
#
# May contain source code from the UCSC CAPES Project:
# Copyright (c) 2016-2017 The Regents of the University of California. All
# rights reserved.
#
# Created by Yan Li <yanli@tuneup.ai>, Kenneth Chang <kchang44@ucsc.edu>,
# Oceane Bel <obel@ucsc.edu>. Storage Systems Research Center, Baskin School
# of Engineering.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Storage Systems Research Center, the
#       University of California, nor the names of its contributors
#       may be used to endorse or promote products derived from this
#       software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# REGENTS OF THE UNIVERSITY OF CALIFORNIA BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
# OF THE POSSIBILITY OF SUCH DAMAGE.
from __future__ import absolute_import, division, print_function, unicode_literals
from typing import Any, List, Optional, Tuple

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

from .common import *
import gc
from .getter_extension_base import GetterExtensionBase
from .protocol_extension_base import *
from .setter_extension_base import SetterExtensionBase
import socket
# This file has to be Python 2/3 compatible
try:
    from queue import Empty, Queue
except ImportError:
    from Queue import Empty, Queue
from threading import RLock
import time
import traceback
from .tulogging import *
from uuid import *


class TUClient:
    """The TuneUp.ai Client Class"""
    def __init__(self, logger, client_id, cluster_name, node_name, api_secret_key, protocol, getters, setters, network_timeout, tick_len=1, debugging_level=0):
        # type: (logging.Logger, UUID, str, str, str, ProtocolExtensionBase, Optional[List[GetterExtensionBase]], Optional[List[SetterExtensionBase]], int, int, int) -> None
        """ Create a TUClient instance

        :param logger: a Logger instance
        :param client_id: the UUID of this client
        :param cluster_name: the name of the cluster this client belongs to
        :param node_name: a string that uniquely identifies this client
        :param protocol: a ProtocolExtensionBase instance
        :param network_timeout: timeout before retrying connection
        :param debugging_level: 0: don't print debug info, 1: print debug info, 2: more debug info
        """
        self._logger = logger
        self._client_id = client_id
        self._cluster_name = cluster_name
        self._node_name = node_name

        _log_instance_name = '{cluster_name}.{node_name}'.format(cluster_name=cluster_name, node_name=node_name)
        logger_set_formatter(logger, name=_log_instance_name)

        self._api_secret_key = api_secret_key
        self._msg_queue = Queue()
        self._protocol = protocol
        self._protocol.set_target_queue(self._msg_queue)
        self._network_timeout = network_timeout
        self._debugging_level = debugging_level
        self._logger.info('Client {name} on {hostname} has been created'.format(name=self._node_name,
                                                                                hostname=socket.gethostname()))
        self._getters = getters
        self._setters = setters
        self._tick_len = tick_len
        self._logger.info('tick_len: {tick_len}'.format(tick_len=tick_len))
        self._setters = setters
        self._stopped = False
        # Whether we should notify gateway about our stop. Used only in tests.
        self.notify_gateway_on_stop = True
        self._last_collect_monotonic_time = 0
        # _last_collect_wall_time is initialized to -1 so that, if tick_len == 0, the first
        # ts we use for sending the collected data will be 0.
        self._last_collect_wall_time = -1
        self._collect_time_decimal = 0.5  # we always collect at the middle of a second
        # ts when we received last feedback from TUGateway or initiated connects, used for checking timeout.
        self._last_received_ts = 0
        self._status = ClientStatus.OFFLINE

        # don't call protocol.connect() because start() may be called in a different process/thread

    def timestamp_and_send_list(self, data, ts=None):
        # type: (List[Any], float) -> None
        assert isinstance(data, list), 'Wrong data type for timestamp_and_send_list'

        # prefix it with the timestamp
        if not ts:
            ts = time.time()
        self._protocol.send_list([ts] + data)
        # Force a context switch
        time.sleep(0)

    def start(self):
        while not self._stopped:
            try:
                self._protocol.start_poller()
                self._start_session()
                self._logger.info('Client node {node_name} session ended'.format(node_name=self._node_name))
            except TUTimeoutError as err:
                self._logger.error('Client node {node_name} timeout error: {err}'.format(node_name=self._node_name,
                                                                                         err=str(err)))
                self._logger.info('Client node {node_name} network protocol disconnected, trying reconnect...'
                                  .format(node_name=self._node_name))
                # Continue if not stopped
            except Exception as err:
                self._logger.error('Client node {node_name} fatal error: {err_name}: {err}'
                                   .format(node_name=self._node_name, err_name=type(err).__name__, err=str(err)))
                self._logger.error(traceback.format_exc())
                # Don't continue on other errors
                return
            finally:
                self._protocol.disconnect()
        self._logger.info('Client node {node_name} stopped'.format(node_name=self._node_name))

    def _start_session(self):
        if self._debugging_level >= 1:
            import cProfile
            import io
            import pstats
            pr = cProfile.Profile()
            pr.enable()
        if self._debugging_level >= 2:
            from pympler.tracker import SummaryTracker
            tracker = SummaryTracker()

        # GC causes unplanned stall and disrupts precisely timed collection.
        # Disable it and do it manually before sleeping.
        gc.disable()
        # Used by steps to customize error message
        current_error_msg = None
        # Whether to force a collect step asap. Used when tick_len == 0.
        if self._tick_len == 0:
            force_collect = True
        try:
            self._logger.info('Client node {node_name} started'.format(node_name=self._node_name))
            while not self._stopped:
                if self._status == ClientStatus.OFFLINE:
                    self._status = ClientStatus.HANDSHAKE1_AUTHENTICATING
                    # Handshake
                    self.timestamp_and_send_list(
                        [ProtocolCode.KEY, self._api_secret_key, self._cluster_name, self._node_name])
                    # Reset the timeout counter after sending out a command
                    self._last_received_ts = monotonic_time()
                    current_error_msg = 'Failed to connect to the gateway'
                    self._logger.info('Client node {node_name} initiated handshaking. Step 1: authenticating...'.format(node_name=self._node_name))

                if self._status == ClientStatus.ALL_OK:
                    if self._getters is not None and len(self._getters) > 0:
                        # We need to collect at a fix time in a second (self._collect_time_decimal) by
                        # the wall clock (so that the wall clock time will be saved to the database for
                        # other analyses), but the second boundary of monotonic_time() is not aligned
                        # with wall clock. That's why we need to calculate the diff between wall clock
                        # and monotonic_time, and subtract that from self._collect_time_decimal.
                        # We assume wall clock is always ahead of monotonic time.
                        monotonic_time_wall_clock_diff = time.time() % 1 - monotonic_time() % 1
                        if monotonic_time_wall_clock_diff < 0:
                            monotonic_time_wall_clock_diff += 1
                        ts = monotonic_time()
                        # When self._tick_len > 0, we do a collect step periodically.
                        # When self._tick_len == 0, we wait until force_collect.
                        if (self._tick_len > 0 and
                            ts - (self._last_collect_monotonic_time + (self._collect_time_decimal - monotonic_time_wall_clock_diff)) >= self._tick_len - 0.01) \
                                or \
                           (self._tick_len == 0 and force_collect):
                            # This must be updated *before* collecting to prevent the send time from
                            # slowly drifting away
                            self._last_collect_monotonic_time = int(ts)
                            if self._tick_len > 0:
                                self._last_collect_wall_time = time.time()
                            else:
                                # When tick_len == 0, we have to use a increasing counter instead of
                                # the read collect time to prevent collision.
                                self._last_collect_wall_time += 1
                            if self._tick_len == 0:
                                force_collect = False
                            pi_data = []
                            for g in self._getters:
                                d = g.collect()
                                if d is None or len(d) == 0:
                                    self._logger.warning('Client node {node_name} getter {g} did not return any data'.format(
                                        node_name=self._node_name, g=g
                                    ))
                                else:
                                    pi_data.extend(d)
                            if len(pi_data) == 0:
                                self._logger.info(
                                    'Client node {node_name} getter returns no data. Skipped sending.'.format(
                                        node_name=self._node_name))
                            else:
                                self._logger.debug('Client node {node_name} collected from all getters: {pi_data}'
                                                   .format(node_name=self._node_name, pi_data=str(pi_data)))
                                self.timestamp_and_send_list([ProtocolCode.PI, pi_data],
                                                             ts=self._last_collect_wall_time)
                                # We don't wait for 'OK' to save time
                        else:
                            pass
                    else:
                        self._last_collect_monotonic_time = monotonic_time()

                gc.collect()
                flush_log()

                # Print out memory usage every minute
                if self._debugging_level >= 2 and int(time.time()) % 60 == 0:
                    print('Time: ' + time.asctime(time.localtime(time.time())))
                    tracker.print_diff()

                if self._status == ClientStatus.ALL_OK and self._getters is not None and len(self._getters) > 0:
                    # Calculate the precise time for next collection
                    sleep_second = self._last_collect_monotonic_time + \
                                   (self._collect_time_decimal - monotonic_time_wall_clock_diff) + \
                                   self._tick_len - \
                                   monotonic_time()
                    sleep_second = max(sleep_second, 0)
                else:
                    sleep_second = 1

                sleep_start_ts = monotonic_time()
                try:
                    msg = self._msg_queue.get(block=True, timeout=sleep_second)
                except Empty:
                    if monotonic_time() - self._last_received_ts > self._network_timeout:
                        err_msg = 'Received no data in {timeout} seconds. Timeout. Reconnecting...'.\
                            format(timeout=self._network_timeout)
                        if current_error_msg is not None:
                            err_msg = current_error_msg + ' ' + err_msg
                        raise TUTimeoutError(err_msg)
                    continue
                finally:
                    self._logger.debug('Slept {0} seconds'.format(monotonic_time() - sleep_start_ts))
                self._last_received_ts = monotonic_time()

                # Remember to use 'continue' after successfully processing requests. Otherwise the default
                # catch-all warning at the bottom will be triggered.
                msg_code = msg[1]
                if msg_code in (ProtocolCode.PI_RECEIVED_OK, ProtocolCode.HEARTBEAT):
                    continue
                elif msg_code == ProtocolCode.BAD_MSG:
                    err_msg = 'Received BAD_MSG reply.'
                    if len(msg) >= 3:
                        err_msg = err_msg + ' ' + str(msg[2])
                    if current_error_msg is not None:
                        err_msg = current_error_msg + ' ' + err_msg
                    raise TUCommunicationError(err_msg)
                elif msg_code == ProtocolCode.WRONG_KEY:
                    if self._status == ClientStatus.HANDSHAKE1_AUTHENTICATING:
                        raise KeyError(current_error_msg + ' Please check API secret key. Exiting...')
                    # For all other status, the default catch all warning below will be issued
                elif msg_code == ProtocolCode.OK:
                    if self._status == ClientStatus.HANDSHAKE1_AUTHENTICATING:
                        self._status = ClientStatus.HANDSHAKE2_UPLOAD_METADATA
                        self._logger.info(
                            'Client node {node_name} authenticated with gateway.'.format(node_name=self._node_name))
                        self._logger.info(
                            'Client node {node_name} handshake step 2: uploading PI and parameter metadata.'.
                            format(node_name=self._node_name))
                        # Send the PI and Parameter Metadata
                        # Merge all PI names to one list
                        pi_metadata = []
                        if self._getters is not None:
                            for getter in self._getters:
                                if getter.pi_names is not None:
                                    assert isinstance(getter.pi_names, list)
                                    pi_metadata += getter.pi_names
                        # Merge all parameter names to one list
                        param_metadata = []
                        if self._setters is not None:
                            for setter in self._setters:
                                if setter.parameter_names is not None:
                                    assert isinstance(setter.parameter_names, list)
                                    param_metadata += setter.parameter_names

                        self.timestamp_and_send_list([ProtocolCode.PI_PARAMETER_META, pi_metadata, param_metadata])
                        # Reset the timeout counter after sending out a command
                        self._last_received_ts = monotonic_time()
                        current_error_msg = 'Failed to register PI and parameter metadata.'
                        continue
                    elif self._status == ClientStatus.HANDSHAKE2_UPLOAD_METADATA:
                        self._status = ClientStatus.ALL_OK
                        self._logger.info(
                            'Client node {node_name} registered PI and Parameter metadata.'.format(
                                node_name=self._node_name))
                        current_error_msg = None
                        continue
                elif msg_code == ProtocolCode.ACTION:
                    actions = msg[2]
                    self._logger.debug('Performing action ' + str(actions))
                    for c in self._setters:
                        c.action(actions)
                    self._logger.debug('Finished performing action.')
                    self.timestamp_and_send_list([ProtocolCode.ACTION_DONE])
                    if self._tick_len == 0:
                        force_collect = True
                    continue
                elif msg_code == ProtocolCode.CLIENT_STATUS:
                    # The ID of the client or CLI tool that was requesting the status report
                    requesting_client_id_in_hex_str = msg[2]
                    self._protocol.client_status_reply(requesting_client_id_in_hex_str, self._cluster_name, self._node_name,
                                                       self._status)
                    continue
                elif msg_code == ProtocolCode.CLUSTER_STATUS:
                    # Query the cluster about its status
                    requesting_client_id_in_hex_str = msg[2]
                    self.timestamp_and_send_list([ProtocolCode.CLUSTER_STATUS, requesting_client_id_in_hex_str])
                    continue
                elif msg_code == ProtocolCode.CLUSTER_STATUS_REPLY:
                    # The ID of the client or CLI tool that was requesting the status report
                    requesting_client_id_in_hex_str = msg[2]
                    cluster_name = msg[3]
                    cluster_status = msg[4]
                    client_list = msg[5]
                    self._protocol.cluster_status_reply(requesting_client_id_in_hex_str, cluster_name, cluster_status,
                                                        client_list)
                    continue
                elif msg_code == ProtocolCode.START_TUNING:
                    # A client (such as lc.py) has requested us to forward START_TUNING to gateway
                    desired_node_count = msg[2]
                    requesting_client_id_in_hex_str = msg[3]
                    self.timestamp_and_send_list([ProtocolCode.START_TUNING, desired_node_count,
                                                  requesting_client_id_in_hex_str])
                    continue
                elif msg_code == ProtocolCode.START_TUNING_REPLY:
                    requesting_client_id_in_hex_str = msg[2]
                    gateway_node_count = msg[3]
                    self._protocol.cluster_start_tuning_reply(requesting_client_id_in_hex_str, gateway_node_count)
                    continue
                elif msg_code == ProtocolCode.CLUSTER_NOT_CONFIGURED:
                    self._logger.info('Cluster not configured yet')
                    continue
                elif msg_code == 'DATALENWRONG':
                    self._logger.error('Client node {node_name} received data length wrong error. Exiting.'
                                       .format(node_name=self._node_name))
                    self.stop()
                    continue
                elif msg_code == ProtocolCode.NOT_AUTH:
                    self._logger.error('Client node {node_name} not authenticated. Try reconnecting...'
                                       .format(node_name=self._node_name))
                    return
                elif msg_code == ProtocolCode.BAD_PI_DATA:
                    self._logger.error('Client node {node_name} received bad PI data error. Exiting.'
                                       .format(node_name=self._node_name))
                    self.stop()
                    continue
                elif msg_code == ProtocolCode.DUPLICATE_PI_DATA:
                    self._logger.error('Client node {node_name} received duplicate PI data error.'
                                       .format(node_name=self._node_name))
                    continue

                # A cache all for all unexpected messages. Don't put this in an 'else', because that would prevent
                # us from catch non-matching conditions from deeper ifs above.
                self._logger.warning('Received unexpected message: {msg}. Client status: {status}.'.format(
                    msg=str(msg), status=str(self._status)))

            if self.notify_gateway_on_stop:
                self.timestamp_and_send_list([ProtocolCode.CLIENT_STOP])
            self._logger.info('Client node {node_name} stopped'.format(node_name=self._node_name))
        finally:
            self._status = ClientStatus.OFFLINE
            gc.enable()

            if self._debugging_level >= 1:
                pr.disable()
                s = io.StringIO()
                sortby = 'cumulative'
                ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
                ps.print_stats()
                print(s.getvalue())

    def stop(self):
        self._logger.info('Requesting TUClient to stop...')
        self._stopped = True
