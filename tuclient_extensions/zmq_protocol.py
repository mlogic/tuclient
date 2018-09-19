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

import errno
import json
import logging
from tuclient import *
from uuid import *
import zlib
import zmq


class ZMQProtocol(ProtocolExtensionBase):
    PROTOCOL_VER = 1

    def __init__(self, logger, client_id, gateway_address):
        # type: (logging.Logger, UUID, str) -> None
        super(ZMQProtocol, self).__init__(logger, client_id)
        self._gateway_address = gateway_address
        self._context = None  # type: Optional[zmq.Context]
        self._socket = None   # type: Optional[zmq.Socket]
        self._poller = None   # type: Optional[zmq.Poller]

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

    @property
    @overrides(ProtocolExtensionBase)
    def connected(self):
        # type: () -> bool
        """Check if a connection has been established"""
        return self._socket is not None

    @overrides(ProtocolExtensionBase)
    def disconnect(self):
        if self._poller is not None:
            if self._socket is not None:
                self._poller.unregister(self._socket)
            self._poller = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        if self._context is not None:
            self._context.destroy()
            self._context = None

    @overrides(ProtocolExtensionBase)
    def receive(self, timeout):
        # type: (int) -> Optional[List[Any]]
        """Block until data arrives
        :param timeout: timeout in how many ms
        :return: received request or None if timeout"""
        start_time = time.time()
        while True:
            time_left = timeout - (time.time() - start_time) * 1000
            if time_left < 0:
                return None
            try:
                p = dict(self._poller.poll(time_left))
            except zmq.ZMQError as e:
                # This is a quirk of older zmq. The old version of pyzmq from EPEL throws out ZMQError
                # when receiving a signal; the latest version of pyzmq doesn't.
                if e.errno == errno.EINTR:
                    # poll again
                    continue
                else:
                    # other error, raise it
                    raise
            if self._socket in p:
                try:
                    data = self._socket.recv()
                    req = json.loads(zlib.decompress(data))
                except (zlib.error, json.decoder.JSONDecodeError) as err:
                    self._logger.error('Failed decoding a message with error {err}: {data}'.format(
                        err=err, data=str(data)))
                    continue

                if req[0] != ZMQProtocol.PROTOCOL_VER:
                    self._logger.error('Protocol version error. Expecting {exp}, got {act}'.format(exp=ZMQProtocol.PROTOCOL_VER, act=req[0]))
                    continue
                if isinstance(req[2], str):
                    return req[2:]
                else:
                    self._logger.error('Corrupted message received: ' + str(req))

    @overrides(ProtocolExtensionBase)
    def send_list(self, data):
        # type: (List[Any]) -> None
        assert isinstance(data, list), 'Wrong data type for send_list'

        # prefix it with the protocol version
        data = [ZMQProtocol.PROTOCOL_VER] + data

        if not self.connected:
            self.connect_to_gateway()
        self._socket.send(zlib.compress(json.dumps(data).encode('ascii')))
        self._logger.debug('Message sent at {ts}'.format(ts=time.time()))
