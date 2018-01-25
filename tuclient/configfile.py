"""ConfigFile of TuneUp.ai Client
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

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

# This file has to be Python 2/3 compatible
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

from tuclient import ConfigBase
from .common import *


class ConfigFile(ConfigBase):
    def __init__(self, logger, *args):
        """Load one or more config files

        The parameter(s) are passed directly to ConfigParser.read().
        """
        super().__init__(logger)
        self._config = ConfigParser()
        print(*args)
        self._logger.info('Loaded config files: ' + str(self._config.read(*args)))

    @overrides(ConfigBase)
    def get_config(self):
        return self._config

    @overrides(ConfigBase)
    def db_type(self):
        dbstr = self._config['global']['db']
        colon_pos = dbstr.index(':')
        return dbstr[:colon_pos]

    @overrides(ConfigBase)
    def db_path(self):
        dbstr = self._config['global']['db']
        colon_pos = dbstr.index(':')
        return dbstr[colon_pos+1:]
