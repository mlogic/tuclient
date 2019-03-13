#!/usr/bin/env bash
# Start a docker container for testing the collectd NGINX extension
# module
#
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
set -euo pipefail
cd `dirname $0`

docker run --name test-nginx-status \
       -d -v `pwd`/nginx_status.conf:/etc/nginx/conf.d/nginx_status.conf:ro \
       -p 8080:80 -p 8081:8080 nginx
