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
from typing import Any, List, Optional

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import gc
from .getter_extension_base import GetterExtensionBase
import pickle
from .protocol_extension_base import ProtocolExtensionBase
from .setter_extension_base import SetterExtensionBase
import socket
import time
from .tulogging import *
import zlib


class TUClient:
    """The TuneUp.ai Client Class"""

    def __init__(self, logger, id, protocol, getters, setters, tick_len=1, debugging_level=0):
        # type: (logging.Logger, int, ProtocolExtensionBase, List[GetterExtensionBase], List[SetterExtensionBase], int, int) -> None
        """ Create a TUClient instance

        :param logger: a Logger instance
        :param id: the ID of this client
        :param protocol: a ProtocolExtensionBase instance
        :param debugging_level: 0: don't print debug info, 1: print debug info, 2: more debug info
        """
        assert isinstance(id, int)
        self._logger = logger
        self._id = id
        self._protocol = protocol
        self._debugging_level = debugging_level
        self._logger.info('Client on {hostname} created with ID {id}'.format(hostname=socket.gethostname(), id=self._id))
        self._getters = getters
        self._setters = setters
        self._tick_len = tick_len
        self._setters = setters
        self._stopped = False
        self._last_collect_second = 0
        self._collect_time_decimal = 0.5  # we always collect at the middle of a second

        # don't call protocol.connect() because start() may be called in a different process/thread

    def timestamp_and_send_list(self, data, ts=None):
        # type: (List[Any], int) -> None
        assert isinstance(data, list), 'Wrong data type for timestamp_and_send_list'

        # prefix it with the timestamp
        if not ts:
            ts = int(time.time())
        self._protocol.send_list([ts] + data)

    def start(self):
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
        self._protocol.connect_to_gateway()

        # GC causes unplanned stall and disrupts precisely timed collection.
        # Disable it and do it manually before sleeping.
        gc.disable()
        try:
            self._logger.info('TUClient started')
            while not self._stopped:
                if self._getters:
                    ts = time.time()
                    if ts - (self._last_collect_second + self._collect_time_decimal) >= self._tick_len - 0.01:
                        # This must be updated *before* collecting to prevent the send time from
                        # slowly drifting away
                        self._last_collect_second = int(ts)
                        result = []
                        for g in self._getters:
                            result.extend(g.collect())
                        self._logger.info('Collected: ' + str(result))
                        self.timestamp_and_send_list(result, ts)
                    else:
                        pass
                else:
                    self._last_collect_second = time.time()

                gc.collect()
                flush_log()

                # Print out memory usage every minute
                if self._debugging_level >= 2 and int(time.time()) % 60 == 0:
                    print('Time: ' + time.asctime(time.localtime(time.time())))
                    tracker.print_diff()

                # Calculate the precise time for next collection
                sleep_second = self._last_collect_second + self._collect_time_decimal + self._tick_len - time.time()
                sleep_second = max(sleep_second, 0)

                sleep_start_ts = time.time()
                req = self._protocol.receive(sleep_second * 1000)
                self._logger.debug('Slept {0} seconds'.format(time.time() - sleep_start_ts))
                if req:
                    cmd = req[2]
                    if req[0] == b'ACTION':
                        actions = req[1:]
                        self._logger.info('Performing action ' + str(actions))
                        for c in self._setter:
                            c.action(actions)
                    else:
                        self._logger.warning('Unknown command received: ' + cmd)

            self._logger.info('TUClient stopped')
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
