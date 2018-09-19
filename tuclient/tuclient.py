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

from collections import deque
import gc
from .getter_extension_base import GetterExtensionBase
from .protocol_extension_base import ProtocolExtensionBase
from .setter_extension_base import SetterExtensionBase
import socket
from threading import RLock
import time
import traceback
from .tulogging import *
from uuid import *


class CommunicationError(Exception):
    pass


# Python 2 doesn't have a builtin TimeoutError
if 'TimeoutError' not in dir():
    class TimeoutError(OSError):
        """ Timeout expired. """
        def __init__(self, *args, **kwargs): # real signature unknown
            pass


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
        self._api_secret_key = api_secret_key
        self._protocol = protocol
        self._network_timeout = network_timeout
        self._debugging_level = debugging_level
        self._logger.info('Client {name} on {hostname} has been created'.format(name=self._node_name,
                                                                                hostname=socket.gethostname()))
        self._getters = getters
        self._setters = setters
        self._tick_len = tick_len
        self._setters = setters
        self._stopped = False
        self._last_collect_second = 0
        self._collect_time_decimal = 0.5  # we always collect at the middle of a second
        self._last_received_ts = 0        # ts when we received last feedback from TUGateway, used for checking timeout.
        # We use a global lock. This is by far only needed by test cases, which a different thread
        # calls our public functions.
        self._lock = RLock()
        # A buffer that is used to store incoming commands when we are waiting for something.
        self._income_data_buffer = deque()

        # don't call protocol.connect() because start() may be called in a different process/thread

    def timestamp_and_send_list(self, data, ts=None):
        # type: (List[Any], float) -> None
        assert isinstance(data, list), 'Wrong data type for timestamp_and_send_list'

        # prefix it with the timestamp
        if not ts:
            ts = time.time()
        with self._lock:
            self._protocol.send_list([ts] + data)
        time.sleep(0)

    def start(self):
        while not self._stopped:
            try:
                self._start_session()
                self._logger.info('Client node {node_name} session ended'.format(node_name=self._node_name))
            except TimeoutError as err:
                self._logger.error('Client node {node_name} timeout error: {err}'.format(node_name=self._node_name,
                                                                                         err=str(err)))
                with self._lock:
                    self._protocol.disconnect()
                self._logger.info('Client node {node_name} network protocol disconnected, trying reconnect...'
                                  .format(node_name=self._node_name))
            except Exception as err:
                self._logger.error('Client node {node_name} fatal error: {err_name}: {err}'
                                   .format(node_name=self._node_name, err_name=type(err).__name__, err=str(err)))
                self._logger.error(traceback.format_exc())
                return
        self._logger.info('Client node {node_name} stopped'.format(node_name=self._node_name))


    def _wait_for(self, reply, error_message):
        """Wait for reply and record error_message if times out"""
        # TODO: This is an ugly hack. We need to use a proper finite-state automaton and merge this with the main message loop.
        with self._lock:
            while True:
                req = self._protocol.receive(self._network_timeout * 1000)
                if req is not None and len(req) >= 1 and isinstance(req[0], str):
                    if req[0] == reply:
                        return
                    elif req[0] == 'HB':
                        continue
                    elif req[0] == 'WRONGKEY':
                        raise KeyError(error_message + ' Please check API secret key. Exiting...')
                    elif req[0] == 'BADMSG':
                        raise KeyError(error_message + ' Received BADMSG reply. Exiting...')
                    elif req[0] == 'ACTION':
                        # We put the ACTION command in a buffer and process it later
                        self._logger.info('Received ACTION command while waiting for {reply}, postponing the ACTION command...'.format(reply=reply))
                        self._income_data_buffer.append(req)
                    else:
                        raise CommunicationError(error_message + ' (got reply {req})'.format(req=req))
                else:
                    raise TimeoutError(error_message + ' (no reply received)')

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

        # ZMQ context must be created here because this function may be executed in a separate
        # process/thread
        with self._lock:
            self._protocol.connect_to_gateway()

        # Handshake
        self.timestamp_and_send_list(['KEY', self._api_secret_key, self._cluster_name, self._node_name])
        self._wait_for('OK', 'Failed to register on a gateway.')
        self._logger.info('Client node {node_name} authenticated with gateway.'.format(node_name=self._node_name))

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

        self.timestamp_and_send_list(['PIPMETA', pi_metadata, param_metadata])
        self._wait_for('OK', 'Failed to register PI and parameter metadata.')
        self._logger.info('Client node {node_name} registered PI and Parameter metadata.'.format(node_name=self._node_name))
        self._last_received_ts = time.time()

        # GC causes unplanned stall and disrupts precisely timed collection.
        # Disable it and do it manually before sleeping.
        gc.disable()
        try:
            self._logger.info('Client node {node_name} started'.format(node_name=self._node_name))
            while not self._stopped:
                if self._getters is not None and len(self._getters) > 0:
                    ts = time.time()
                    if ts - (self._last_collect_second + self._collect_time_decimal) >= self._tick_len - 0.01:
                        # This must be updated *before* collecting to prevent the send time from
                        # slowly drifting away
                        self._last_collect_second = int(ts)
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
                                'Client node {node_name} no getter returns data. Skipped sending.'.format(
                                    node_name=self._node_name))
                        else:
                            self._logger.info('Client node {node_name} collected from all getters: {pi_data}'
                                              .format(node_name=self._node_name, pi_data=str(pi_data)))
                            self.timestamp_and_send_list(['PI', pi_data])
                            # We don't wait for 'OK' to save time
                    else:
                        pass
                else:
                    self._last_collect_second = time.time()

                gc.collect()
                flush_log()
                time.sleep(0)

                # Print out memory usage every minute
                if self._debugging_level >= 2 and int(time.time()) % 60 == 0:
                    print('Time: ' + time.asctime(time.localtime(time.time())))
                    tracker.print_diff()

                # Calculate the precise time for next collection
                sleep_second = self._last_collect_second + self._collect_time_decimal + self._tick_len - time.time()
                sleep_second = max(sleep_second, 0)

                if len(self._income_data_buffer) != 0:
                    req = self._income_data_buffer.popleft()
                    self._logger.info('Processing the postponed {cmd} command...'.format(cmd=req[0]))
                else:
                    sleep_start_ts = time.time()
                    with self._lock:
                        req = self._protocol.receive(sleep_second * 1000)
                    self._logger.debug('Slept {0} seconds'.format(time.time() - sleep_start_ts))
                if req:
                    self._last_received_ts = time.time()
                    cmd = req[0]
                    if cmd == 'ACTION':
                        actions = req[1]
                        self._logger.info('Performing action ' + str(actions))
                        for c in self._setters:
                            c.action(actions)
                        self._logger.info('Finished performing action.')
                        self.timestamp_and_send_list(['ACTIONDONE'])
                    elif cmd == 'OK' or cmd == 'HB':
                        pass
                    elif cmd == 'DATALENWRONG':
                        self._logger.error('Client node {node_name} received data length wrong error. Exiting.'
                                           .format(node_name=self._node_name))
                        self.stop()
                    elif cmd == 'NOTAUTH':
                        self._logger.error('Client node {node_name} not authenticated. Try reconnecting...'
                                           .format(node_name=self._node_name))
                        return
                    elif cmd == 'BADPIDATA':
                        self._logger.error('Client node {node_name} received bad PI data error. Exiting.'
                                           .format(node_name=self._node_name))
                        self.stop()
                    elif cmd == 'DUPLICATEDPIDATA':
                        self._logger.error('Client node {node_name} received duplicate PI data error.'
                                           .format(node_name=self._node_name))
                    else:
                        self._logger.warning('Unknown command received: ' + cmd)

                # Check timeout
                if time.time() - self._last_received_ts > self._network_timeout:
                    self._logger.warning(
                        'Client node {node_name} received no response for more than {timeout} seconds. Reconnecting...'
                            .format(node_name=self._node_name, timeout=self._network_timeout))
                    return

            self.timestamp_and_send_list(['CLIENTSTOP'])
            self._logger.info('Client node {node_name} stopped'.format(node_name=self._node_name))
        finally:
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
