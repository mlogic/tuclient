"""ProtocolExtensionBase class"""
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
from typing import Any, List, Optional, Tuple

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import abc
from .common import *
import logging
from uuid import UUID
# This file has to be Python 2/3 compatible
try:
    from queue import Queue
except ImportError:
    from Queue import Queue


class TUCommunicationError(Exception):
    def __init__(self, msg=None):
        self.msg = msg

    def __str__(self):
        return str(self.msg)


class TUTimeoutError(Exception):
    def __init__(self, msg=None):
        self.msg = msg

    def __str__(self):
        return str(self.msg)


class ProtocolExtensionBase(object):
    """Base class for the protocol to communicate with TUGateway

    Beside sending messages, this class maintains a receiving poller thread that forwards
    messages from the TUGateway to a target queue, which will then be handled by the main
    thread.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, logger, client_id):
        # type: (logging.Logger, UUID) -> None
        self._logger = logger
        self._client_id = client_id
        self._target_queue = None     # type: Optional[Queue]

    def __del__(self):
        self.disconnect()

    def set_target_queue(self, target_queue):
        """Main thread calls this method to pass in a queue for storing received messages"""
        self._target_queue = target_queue

    @abc.abstractmethod
    def start_poller(self):
        """Start poller thread

        Call this method before sending or receiving anything."""
        assert self._target_queue is not None

    @property
    @abc.abstractmethod
    def started(self):
        # type: () -> bool
        """Check the status of the poller"""
        pass

    @abc.abstractmethod
    def disconnect(self):
        """Close a connection

        Call this method if you need to manually close a connection. It will be called
        automatically upon exit. This method should be idempotent."""
        pass

    @abc.abstractmethod
    def send_list(self, data):
        # type: (List[Any]) -> None
        """Send a list

        :param data : a list that can be JSON dumped"""
        pass

    @abc.abstractmethod
    def client_status(self):
        # type: () -> ClientStatus
        """Query the status of the client"""
        pass

    @abc.abstractmethod
    def client_status_reply(self, client_id_in_hex_str, cluster_name, node_name, client_status):
        # type: (str, str, str, ClientStatus) -> None
        """Return client_status to a client

        This is used by tuclient to reply to an asynchronous status query.

        :param client_id_in_hex_str: UUID is not JSON serializable so we use uuid.hex here
        :param cluster_name: name of the cluster
        :param node_name: name of the node
        :param client_status: status of the client to reply to the querying client"""
        pass

    @abc.abstractmethod
    def cluster_status(self):
        # type: () -> Tuple[str, ClusterStatus, List[str, str, ClientStatus]]
        """Query the status of the cluster"""
        pass

    @abc.abstractmethod
    def cluster_status_reply(self, client_id_in_hex_str, cluster_name, cluster_status, client_list):
        # type: (str, str, ClusterStatus, List[str, str, ClientStatus]) -> None
        """Return client_status to a client

        This is used by tuclient to reply to an asynchronous status query.

        :param client_id_in_hex_str: UUID is not JSON serializable so we use uuid.hex here
        :param cluster_name: name of the cluster
        :param cluster_status: status of the cluster
        :param client_list: list of known clients of the cluster as (client_id, client_name, client status)"""
        pass

    @abc.abstractmethod
    def cluster_start_tuning(self, desired_node_count):
        # type: (int) -> List[ProtocolCode, int]
        """Instruct a cluster to start tuning

        tuclient calls this function to instruct a cluster to start tuning when all desired nodes are online.

        If the instruction was successful and the cluster has started tuning, returns desired_node_count.
        Otherwise, return the node_count that the gateway has seen so far, which would be different
        from the desired_node_count.

        :param desired_node_count: desired number of nodes
        :return: result and actual number of nodes"""
        pass

    @abc.abstractmethod
    def cluster_start_tuning_reply(self, reply_protocol_code, client_id_in_hex_str, gateway_node_count):
        # type: (ProtocolCode, str, int]) -> None
        """Send a start_tuning reply to client_id_in_hex_str

        tuclient calls this function to send back a reply to the START_TUNING request to
        the client with client_id_in_hex_str."""
        pass
