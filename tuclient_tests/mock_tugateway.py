#!/usr/bin/env python
"""Mock TUGateway
"""
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
from typing import Any, Dict, List

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import threading
from tuclient import *
from uuid import *
import zlib
import zmq


class MockTUGateway(object):
    PROTOCOL_VER = 1

    def __init__(self, logger, listen_on='127.0.0.1:7777'):
        self._logger = logger
        self._listen_on = listen_on
        self._cluster_name = None
        self._cluster_status = ClusterStatus.NOT_SETUP
        self._stopped = False
        self._clients_status = dict()  # type: Dict[UUID, ClientStatus]
        self._clients_name = dict()    # type: Dict[UUID, str]
        self._thread = threading.Thread(target=self._thread_func)
        self._thread.start()

    def __del__(self):
        self.stop()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def stop(self):
        # Must be idempotent
        if self._thread is not None:
            self._stopped = True
            self._thread.join()
            self._thread = None

    def _send_to_client(self, client_id, obj):
        # type: (UUID, List[Any]) -> None
        """Send json'ed obj to a client

        Could only be called within the worker thread. Socket must NOT be busy.
        """
        self._socket.send(client_id.bytes, zmq.SNDMORE)
        # Prepend obj with PROTOCOL VERSION and time stamp
        if not isinstance(obj, list):
            obj = [obj, ]
        obj = [MockTUGateway.PROTOCOL_VER, time.time()] + obj
        self._socket.send(zlib.compress(json.dumps(obj, cls=EnumEncoder).encode('ascii')))

    def _thread_func(self):
        try:
            self._worker_loop()
        except Exception as err:
            self._logger.error('MockTUGateway fatal error: {err_name}: {err}'
                               .format(err_name=type(err).__name__, err=str(err)))
            self._logger.error(traceback.format_exc())
            # Force exit in case of any uncaught exception because that means there's
            # something wrong with your test case.
            os._exit(1)

    def _worker_loop(self):
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.ROUTER)
        self._socket.bind('tcp://' + self._listen_on)
        self._logger.info('Listening on ' + self._listen_on)
        self._poller = zmq.Poller()
        self._poller.register(self._socket, zmq.POLLIN)
        self._logger.info('MockTUGateway started')

        while not self._stopped:
            p = dict(self._poller.poll(100))
            if self._socket not in p:
                continue
            client_id = UUID(bytes=self._socket.recv())
            payload = self._socket.recv()
            req = json.loads(zlib.decompress(payload), object_hook=as_enum)

            if len(req) < 2:
                self._logger.error('Received a corrupted message: message too short (length is {len}).'.
                                   format(len=len(req)))
                continue
            if req[0] != MockTUGateway.PROTOCOL_VER:
                self._logger.error('Received a message with unsupported protocol version {ver}'.format(ver=req[0]))
                continue

            if req[2] == ProtocolCode_KEY:
                self._clients_status[client_id] = ClientStatus.HANDSHAKE1_AUTHENTICATING
                self._clients_name[client_id] = req[5]
                if self._cluster_name is None:
                    self._cluster_name = req[4]
                else:
                    if self._cluster_name != req[4]:
                        raise RuntimeError('Client sent in wrong cluster name')

                self._send_to_client(client_id, [ProtocolCode_OK])
                continue

            if client_id not in self._clients_status:
                raise RuntimeError('Client {client_id} not authenticated. Exiting.'.
                                   format(client_id=client_id))

            if req[2] == ProtocolCode_PI_PARAMETER_META:
                if self._clients_status[client_id] == ClientStatus.HANDSHAKE1_AUTHENTICATING:
                    self._clients_status[client_id] = ClientStatus.ALL_OK
                    self._send_to_client(client_id, [ProtocolCode_OK])
                    continue
                else:
                    raise RuntimeError('Received ProtocolCode_PI_PARAMETER_META at the wrong time. Exiting.')
            elif req[2] == ProtocolCode_CLUSTER_STATUS:
                requesting_client_id_in_hex_str = req[3]
                self._send_to_client(client_id, [ProtocolCode_CLUSTER_STATUS_REPLY, requesting_client_id_in_hex_str,
                                                 self._cluster_name, self._cluster_status,
                                                 [(client_id.hex, self._clients_name[client_id], self._clients_status[client_id]) for client_id in self._clients_status.keys()]])

        self._logger.debug('mock_tugateway stopped')


if __name__ == '__main__':
    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.WARNING)

    gateway_addr = '127.0.0.1:7777'
    with MockTUGateway(logger, gateway_addr):
        print('MockTUGateway started')
        while True:
            time.sleep(1)
