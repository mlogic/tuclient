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

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import errno
import threading
from tuclient import *
from uuid import *
import zlib
import zmq


def zmq_recv_message(logger, sock, with_id):
    # type: (logging.Logger, zmq.socket, bool) -> List[Any]
    """Receive and verify a message from sock

    This method doesn't poll and will block forever if there's nothing to receive from sock. Use
    :func:`_poll_and_recv_message`.

    :param logger: a logger to use
    :param sock: the ZMQ socket to receive from
    :param with_id: whether we need to receive an ID before payload
    :return: Received payload. If with_id is True, returns [ID, Payload]."""

    if with_id:
        client_id_bytes = sock.recv()
        try:
            client_id = UUID(bytes=client_id_bytes)
        except ValueError:
            logger.error('Received corrupted client_id "{client_id_bytes}"'.
                         format(client_id_bytes=str(client_id_bytes)))
            raise

    data = sock.recv()
    try:
        data = zlib.decompress(data)
        # The decode() is not needed for Python 3 but is required by Python 2.7,
        # which cannot tell byte string and Unicode apart.
        data = data.decode('utf8')
        msg = json.loads(data, object_hook=as_enum)
    except JSONDecodeError as err:
        logger.error('Failed decoding a command message with error {err}: {data}'.format(
            err=err, data=str(data)))
        raise
    if msg[0] != ZMQProtocol.PROTOCOL_VER:
        raise TUCommunicationError('Command message protocol version error. Expecting {exp}, got {act}'.
                                   format(exp=ZMQProtocol.PROTOCOL_VER, act=msg[0]))

    if with_id:
        logger.debug('Received message from {client_id}: {msg}'.format(client_id=client_id, msg=str(msg)))
        return [client_id, msg]

    else:
        logger.debug('Received message ' + str(msg))
        return msg


def zmq_poll_and_recv_message(logger, sock, timeout=10):
    # type: (logging.Logger, zmq.socket, int) -> Optional[List[Any]]
    """Receive, verify, and parse a message according to the protocol

    This function returns the message received.

    :param timeout: timeout in seconds"""
    poller = None
    try:
        poller = zmq.Poller()
        poller.register(sock, zmq.POLLIN)

        start_time = monotonic_time()
        while True:
            time_left = timeout - (monotonic_time() - start_time)
            if time_left < 0:
                raise TUTimeoutError('Timeout, no message received')
            try:
                p = dict(poller.poll(time_left*1000))
            except zmq.ZMQError as e:
                # This is a quirk of older zmq. The old version of pyzmq from EPEL throws out ZMQError
                # when receiving a signal; the latest version of pyzmq doesn't.
                if e.errno == errno.EINTR:
                    # poll again
                    continue
                else:
                    # other error, raise it
                    raise

            if sock in p:
                return zmq_recv_message(logger, sock, with_id=False)
    finally:
        if poller is not None:
            poller.unregister(sock)
            del poller


def _zmq_send_list(logger, sock, data, client_id=None):
    if client_id is not None:
        sock.send(client_id.bytes, zmq.SNDMORE)

    # prefix it with the protocol version
    data = [ZMQProtocol.PROTOCOL_VER] + data

    sock.send(zlib.compress(json.dumps(data, cls=EnumEncoder).encode('utf8')))
    logger.info('Message sent using socket {sock} at {ts}: {data}'.format(sock=str(sock), ts=time.time(),
                                                                          data=str(data)))


def zmq_send_to(logger, sock, data, client_id=None):
    # type: (logging.Logger, zmq.socket, List[Any], Optional[UUID]) -> None
    """Send a list of data after prefixing a timestamp using a socket

    This function must only be called within the poller thread.

    :param client_id: The UUID of the receiving client. If none, no UUID will be sent."""
    assert isinstance(data, list), 'Wrong data type for send_list'
    _zmq_send_list(logger, sock, [time.time()] + data, client_id)


def zmq_send_to_router(logger, target, data, wait_for_reply=False):
    # type: (logging.Logger, str, List[Any], bool) -> Optional[Any]
    """Send a list of data to a router address using TU protocol

    A random UUID will be generated as client UUID.

    This function is thread-safe."""
    context = None
    s = None
    try:
        context = zmq.Context()
        s = context.socket(zmq.DEALER)
        # http://api.zeromq.org/4-1:zmq-setsockopt#toc16
        tmp_uuid = uuid1()
        s.setsockopt(zmq.IDENTITY, tmp_uuid.bytes)
        s.setsockopt(zmq.SNDTIMEO, 1000)
        s.connect(target)
        zmq_send_to(logger, s, data)
        if wait_for_reply:
            msg = zmq_poll_and_recv_message(logger, s)
            return msg[1:]
    finally:
        if s is not None:
            s.close()
        if context is not None:
            context.destroy()


class ZMQProtocol(ProtocolExtensionBase):
    """Implements ProtocolExtensionBase using ZMQ

    ZMQProtocol can being used to either communicate with the gateway or as a controller to talk
    to an existing tuclient.

    When being used to communicate with the gateway, ZMQProtocol creates a worker thread to
    handle all communications in a non-blocking manner. The messages that it receives from the
    gateway are forwarded to a target queue, which will then be handled by tuclient or other
    owners. It also exposes a controller ZMQ listener that can be used to send commands to the
    worker thread or tuclient.
    """
    PROTOCOL_VER = 1

    def __init__(self, logger, client_id, gateway_address=None, cmd_socket_addr=None):
        # type: (logging.Logger, UUID, Optional[str], Optional[str]) -> None
        """Create a ZMQProtocol instance

        :param gateway_address: the IP and port of gateway, can be left empty when being used as a tuclient
        controller"""
        super(ZMQProtocol, self).__init__(logger, client_id)
        self._gateway_address = gateway_address
        self._context = None         # type: Optional[zmq.Context]
        # The ZMQ socket for connecting to the gateway
        self._gateway_socket = None  # type: Optional[zmq.Socket]
        self._cmd_socket = None      # type: Optional[zmq.Socket]
        self._poller = None          # type: Optional[zmq.Poller]
        self._poller_thread = None   # type: Optional[threading.Thread]
        self._cmd_socket_addr = 'tcp://127.0.0.1:7778' if cmd_socket_addr is None else cmd_socket_addr

    @overrides(ProtocolExtensionBase)
    def start_poller(self):
        # type: () -> None
        super(ZMQProtocol, self).start_poller()
        assert self._poller_thread is None
        self._poller_thread = threading.Thread(target=self._poller_thread_func)
        self._poller_thread.start()

    def _poller_thread_func(self):
        # type: () -> None
        # ZMQ context has to be initialized within the thread
        try:
            self._zmq_init()
            self._poller_loop()
        except Exception as err:
            self._logger.error('ZMQProtocol poller thread fatal exception: {err_name}: {err}'
                               .format(err_name=type(err).__name__, err=str(err)))
            self._logger.error(traceback.format_exc())
        finally:
            self._zmq_uninit()

    def _zmq_init(self):
        # type: () -> None
        """Connect to gateway"""
        if not self._context:
            self._context = zmq.Context()
        self._gateway_socket = self._context.socket(zmq.DEALER)
        # http://api.zeromq.org/4-1:zmq-setsockopt#toc16
        self._gateway_socket.setsockopt(zmq.IDENTITY, self._client_id.bytes)
        # Don't wait if there's any linger messages upon close.
        self._gateway_socket.setsockopt(zmq.LINGER, 0)
        self._logger.info('Connecting to ' + self._gateway_address)
        self._gateway_socket.connect(self._gateway_address)

        # We use ROUTER/DEALER for command socket so that we can have multiple incoming
        # connections.
        self._cmd_socket = self._context.socket(zmq.ROUTER)
        self._cmd_socket.set_hwm(5000)
        self._logger.info('Binding to command socket ' + self._cmd_socket_addr)
        self._cmd_socket.bind(self._cmd_socket_addr)

        self._poller = zmq.Poller()
        self._poller.register(self._gateway_socket, zmq.POLLIN)
        self._poller.register(self._cmd_socket, zmq.POLLIN)

    def _zmq_uninit(self):
        if self._poller is not None:
            if self._cmd_socket is not None:
                self._poller.unregister(self._cmd_socket)
            if self._gateway_socket is not None:
                self._poller.unregister(self._gateway_socket)
            self._poller = None
        if self._gateway_socket is not None:
            self._gateway_socket.close()
            self._gateway_socket = None
        if self._cmd_socket is not None:
            self._cmd_socket.close()
            self._cmd_socket = None
        if self._context is not None:
            self._context.destroy()
            self._context = None

    @property
    @overrides(ProtocolExtensionBase)
    def started(self):
        # type: () -> bool
        """Check the status of the poller

        This function is thread-safe."""
        return self._gateway_socket is not None

    def _poller_loop(self):
        # type: () -> None
        while True:
            try:
                p = dict(self._poller.poll(1000))
            except zmq.ZMQError as e:
                # This is a quirk of older zmq. The old version of pyzmq from EPEL throws out ZMQError
                # when receiving a signal; the latest version of pyzmq doesn't.
                if e.errno == errno.EINTR:
                    # poll again
                    continue
                else:
                    # other error, raise it
                    raise
            if self._gateway_socket in p:
                try:
                    msg = zmq_recv_message(self._logger, self._gateway_socket, with_id=False)
                except (ValueError, JSONDecodeError, TUCommunicationError):
                    continue
                self._target_queue.put(msg[1:])
            elif self._cmd_socket in p:
                client_id, msg = zmq_recv_message(self._logger, self._cmd_socket, with_id=True)
                if msg[2] == ProtocolCode.SEND:
                    # msg[3] is already a ts. Don't add our own timestamp.
                    _zmq_send_list(self._logger, self._gateway_socket, msg[3:])
                elif msg[2] in (ProtocolCode.CLIENT_STATUS, ProtocolCode.CLUSTER_STATUS):
                    self._logger.debug('Request {req} received, forwarding to target queue...'.format(req=str(msg[2])))
                    self._target_queue.put(msg[1:3] + [client_id.hex])
                elif msg[2] == ProtocolCode.START_TUNING:
                    self._logger.debug('Request {req} received, forwarding to target queue...'.format(req=str(msg[2])))
                    self._target_queue.put(msg[1:4] + [client_id.hex])
                elif msg[2] in (ProtocolCode.CLIENT_STATUS_REPLY, ProtocolCode.CLUSTER_STATUS_REPLY,
                                ProtocolCode.START_TUNING_REPLY):
                    sending_to_client_id = UUID(hex=msg[3])
                    payload = msg[3:]
                    zmq_send_to(self._logger, self._cmd_socket, payload, sending_to_client_id)
                elif msg[2] == ProtocolCode.EXIT:
                    self._logger.info('Received exit command from {client_id}. Stopping poller loop...'.
                                      format(client_id=client_id))
                    return
                else:
                    self._logger.error('Corrupted message received: ' + str(msg))

    @overrides(ProtocolExtensionBase)
    def send_list(self, data):
        """Send a list to gateway

        The message is forwarded to the poller thread, which controls the ZMQContext
        and will do the actual sending, through the command socket."""
        zmq_send_to_router(self._logger, self._cmd_socket_addr, [ProtocolCode.SEND] + data)

    @overrides(ProtocolExtensionBase)
    def disconnect(self):
        """Close a connection

        Call this method if you need to manually close a connection. It will be called
        automatically upon exit. This method is NOT thread-safe but should be idempotent."""
        if self._poller_thread is not None:
            self._logger.info('Requesting poller to stop...')
            zmq_send_to_router(self._logger, self._cmd_socket_addr, [ProtocolCode.EXIT])
            self._poller_thread.join()
            self._poller_thread = None

    def client_status(self):
        # type: () -> Tuple[str, str, str, ClientStatus]
        """Query the client status through command socket"""
        msg = zmq_send_to_router(self._logger, self._cmd_socket_addr, [ProtocolCode.CLIENT_STATUS], wait_for_reply=True)
        client_id_str = msg[1]
        cluster_name = msg[2]
        client_node_name = msg[3]
        client_status = msg[4]
        return client_id_str, cluster_name, client_node_name, client_status

    @overrides(ProtocolExtensionBase)
    def client_status_reply(self, client_id_in_hex_str, cluster_name, node_name, client_status):
        # type: (str, str, str, ClientStatus) -> None
        """Send a status reply to client_id

        tuclient calls this function to send back a reply to the CLIENT_STATUS request to
        the client with client_id."""
        zmq_send_to_router(self._logger, self._cmd_socket_addr, [ProtocolCode.CLIENT_STATUS_REPLY, client_id_in_hex_str,
                                                                 cluster_name, node_name, client_status], wait_for_reply=False)

    @overrides(ProtocolExtensionBase)
    def cluster_status(self):
        # type: () -> Tuple[str, ClusterStatus, List[str, str, ClientStatus]]
        """Query the client status through command socket"""
        msg = zmq_send_to_router(self._logger, self._cmd_socket_addr, [ProtocolCode.CLUSTER_STATUS], wait_for_reply=True)
        cluster_name = msg[2]
        cluster_status = msg[3]
        client_list = msg[4]
        return cluster_name, cluster_status, client_list

    @overrides(ProtocolExtensionBase)
    def cluster_status_reply(self, client_id_in_hex_str, cluster_name, cluster_status, client_list):
        # type: (str, str, ClusterStatus, List[str, str, ClientStatus]) -> None
        """Send a cluster status reply to client_id

        tuclient calls this function to send back a reply to the CLUSTER_STATUS request to
        the client with client_id."""
        zmq_send_to_router(self._logger, self._cmd_socket_addr, [ProtocolCode.CLUSTER_STATUS_REPLY, client_id_in_hex_str,
                                                                 cluster_name, cluster_status, client_list],
                           wait_for_reply=False)

    @overrides(ProtocolExtensionBase)
    def cluster_start_tuning(self, desired_node_count):
        # type: (int) -> int
        """Instruct a cluster to start tuning

        tuclient calls this function to instruct a cluster to start tuning when all desired nodes are online.

        If the instruction was successful and the cluster has started tuning, returns desired_node_count.
        Otherwise, return the node_count that the gateway has seen so far, which would be different
        from the desired_node_count.

        :param desired_node_count: desired number of nodes
        :return: actual number of nodes"""
        msg = zmq_send_to_router(self._logger, self._cmd_socket_addr, [ProtocolCode.START_TUNING, desired_node_count],
                                 wait_for_reply=True)
        return msg[2]

    @overrides(ProtocolExtensionBase)
    def cluster_start_tuning_reply(self, client_id_in_hex_str, gateway_node_count):
        # type: (str, int]) -> None
        """Send a start_tuning reply to client_id_in_hex_str

        tuclient calls this function to send back a reply to the START_TUNING request to
        the client with client_id_in_hex_str."""
        zmq_send_to_router(self._logger, self._cmd_socket_addr, [ProtocolCode.START_TUNING_REPLY, client_id_in_hex_str,
                                                                 gateway_node_count],
                           wait_for_reply=False)
