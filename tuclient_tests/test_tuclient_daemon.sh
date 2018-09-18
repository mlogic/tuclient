#!/bin/bash
# Test the TuneUp.ai Client Daemon
# 
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
set -e -u
cd `dirname $0`/..

TMPFILE=`mktemp`
TUCLIENT_SERVICE_CMD="./tuclient_daemon.sh -c tuclient_tests/test_client_conf.ini"
$TUCLIENT_SERVICE_CMD status &>$TMPFILE
grep -q "not running" $TMPFILE

rm -f /tmp/test_tuclient_log.txt
trap "{ $TUCLIENT_SERVICE_CMD stop; exit 255; }" EXIT
$TUCLIENT_SERVICE_CMD start
sleep 3
$TUCLIENT_SERVICE_CMD status &>$TMPFILE
grep -q "is running as" $TMPFILE
# Testing collection is commented out for now, because a client doesn't collect
# until it connects to a gateway.
#grep -q "Collected: \[1, 2\]" /tmp/test_tuclient_log.txt

trap "" EXIT
$TUCLIENT_SERVICE_CMD stop
sleep 2
grep -q "Client node .* stopped" /tmp/test_tuclient_log.txt
$TUCLIENT_SERVICE_CMD status &>$TMPFILE
grep -q "not running" $TMPFILE

echo $0 PASS
