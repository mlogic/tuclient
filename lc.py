#!/usr/bin/env python
"""TuneUp.ai Admin Tool"""
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

import argparse
import logging
import sys
from tuclient import ClientStatusToStrMapping, get_console_logger
from tuclient_extensions import ZMQProtocol
from uuid import uuid1

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'


logger = get_console_logger()


def client_handler(sub_args):
    if sub_args.status is not None:
        # Create a controller to talk to client1
        client_controller = ZMQProtocol(logger, uuid1())
        logger.info('Querying the status of the client running on the local machine...')
        client_id_str, cluster_name, client_node_name, client_status = client_controller.status()
        logger.info('Got the status reply')
        print('Cluster name: ' + cluster_name)
        print('Client node name: ' + client_node_name)
        print('Client ID: ' + client_id_str)
        print('Local client status: ' + ClientStatusToStrMapping[client_status])


def cluster_handler(sub_args):
    if sub_args.status is not None:
        print('Cluster status')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TuneUp.ai Admin Tool')
    parser.add_argument('-v', '--verbose', action='store_true', help='enable verbose mode')
    subparsers = parser.add_subparsers(help='list of commands:', dest='command')
    subparsers.required = True

    parser_client = subparsers.add_parser('client', help='managing a client')
    parser_client.add_argument('status', help='Show the status of clients')
    parser_client.set_defaults(func=client_handler)

    parser_cluster = subparsers.add_parser('cluster', help='managing a cluster')
    parser_cluster.add_argument('status', help='Show the status of the cluster')
    parser_cluster.set_defaults(func=cluster_handler)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(2)
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)
    args.func(args)
