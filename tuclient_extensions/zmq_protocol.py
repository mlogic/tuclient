"""ZMQProtocol class"""
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
from typing import Any, List

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import logging
from tuclient import *
from uuid import *
import zmq


class ZMQProtocol(ProtocolExtensionBase):
    PROTOCOL_VER = 1

    def __init__(self, logger, client_id, gateway_address):
        # type: (logging.Logger, UUID, str) -> None
        super().__init__(logger, client_id)
        self._gateway_address = gateway_address
        self._context = None  # type: Optional[zmq.Context]
        self._socket = None   # type: Optional[zmq.Socket]
        self._poller = None   # type: Optional[zmq.Poller]
        self._heartbeat_ts = None  # type: Optional[int]

    @overrides(ProtocolExtensionBase)
    def connect_to_gateway(self):
        # type: () -> None
        """Connect to gateway"""
        if not self._context:
            self._context = zmq.Context()
        self._socket = self._context.socket(zmq.DEALER)
        # http://api.zeromq.org/4-1:zmq-setsockopt#toc16
        self._socket.setsockopt(zmq.IDENTITY, self._client_id.bytes)
        # Don't wait if there's any linger messages upon close.
        self._socket.setsockopt(zmq.LINGER, 0)
        target = 'tcp://{gateway}'.format(gateway=self._gateway_address)
        self._logger.info('Connecting to ' + target)
        self._socket.connect(target)

        self._poller = zmq.Poller()
        self._poller.register(self._socket, zmq.POLLIN)

        self._heartbeat_ts = time.time()

    @property
    @overrides(ProtocolExtensionBase)
    def connected(self):
        # type: () -> bool
        """Check if a connection has been established"""
        return self._socket is not None

    @overrides(ProtocolExtensionBase)
    def disconnect(self):
        if self._poller:
            if self._socket:
                self._poller.unregister(self._socket)
            self._poller = None
        if self._socket:
            self._socket.close()
            self._socket = None
        if self._context:
            self._context = None

    @overrides(ProtocolExtensionBase)
    def receive(self, timeout):
        # type: (int) -> Optional[List[Any]]
        """Block until data arrives
        :param timeout: timeout in how many ms
        :return: received request or None if timeout or heartbeat is received"""
        p = dict(self._poller.poll(timeout))
        if self._socket in p:
            req = pickle.loads(zlib.decompress(self._socket.recv()))
            assert req[0] == ZMQProtocol.PROTOCOL_VER,\
                'Protocol version error. Expecting {exp}, got {act}'.format(exp=ZMQProtocol.PROTOCOL_VER, act=req[0])
            if isinstance(req[2], bytes):
                # Update heartbeat after receiving any command
                self._heartbeat_ts = time.time()
                cmd = req[2]
                if cmd == b'HB':
                    self._logger.debug('Received heartbeat')
                else:
                    return req[2:]
            else:
                self._logger.error('Corrupted message received: ' + req)
        else:
            if time.time() - self._heartbeat_ts > 5:
                self._logger.warning('No heartbeat for 5 seconds')
                # TODO: Do we need to do something like the following to reconnect here?
                # self.disconnect()
                # self.connect_to_gateway()
                #
                # self._logger.warning('Connection timeout, reconnected')
                self._heartbeat_ts = time.time()
        return None

    @overrides(ProtocolExtensionBase)
    def send_list(self, data):
        # type: (List[Any]) -> None
        assert isinstance(data, list), 'Wrong data type for send_list'

        # prefix it with the protocol version
        data = [ZMQProtocol.PROTOCOL_VER] + data

        if not self.connected:
            self.connect_to_gateway()
        self._socket.send(zlib.compress(pickle.dumps(data)))
        self._logger.debug('Message sent at {ts}'.format(ts=time.time()))
