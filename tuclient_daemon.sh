#!/bin/bash
# TuneUp.ai Client Daemon Control Script
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
cd `dirname $0`

usage() {
    cat <<EOF
Usage: $0 module conffile <start|stop|status>
EOF
}

CONFFILE=/etc/tuclient/tuclient.ini
ARGS=()
while getopts "c:n:" var; do
    case $var in
        c)
            CONFFILE=$OPTARG
            ;;
        n)
            ARGS+=(-n $OPTARG)
            ;;
	?)
            echo "Unknown argument"
            usage
	    exit 2
            ;;
    esac
done
shift $(( $OPTIND - 1 ))
ARGS+=(-c "$CONFFILE")
CMD=$1
MODULE=tuclient

PIDFILE=`grep pidfile $CONFFILE | cut -d"=" -f 2`
if [ -z "$PIDFILE" ]; then
    PIDFILE=`grep pidfile tuclient/default_conf_file.ini | cut -d"=" -f 2`
fi

if [ "$CMD" = "start" ]; then
    python tuclientd.py "${ARGS[@]}"
elif [ "$CMD" = "stop" ]; then
    if [ ! -e $PIDFILE ]; then
        echo "$PIDFILE doesn't exist. Can't find the running process."
        exit 3
    fi
    kill -TERM `cat $PIDFILE`
elif [ "$CMD" = "status" ]; then
    if [ -e $PIDFILE ]; then
        PID=`cat $PIDFILE`
        if ps -ef | grep -v grep | grep -q " ${PID} "; then
            echo "$1 is running as `cat $PIDFILE`"
        else
            rm "$PIDFILE"
            echo "$1 is not running"
        fi
    else
        echo "$1 is not running"
    fi
else
    echo "${CMD}: unknown command"
    exit 255
fi
