"""ConfigFile of TuneUp.ai Client"""
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
from typing import List, Optional, Union

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

# This file has to be Python 2/3 compatible
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

import logging
from tuclient import ConfigBase
from .common import *


class ConfigFile(ConfigBase):
    def __init__(self, logger, system_type, host_name, filenames, default=None):
        # type: (Optional[logging.Logger], Optional[str], Optional[str], Union[str, List[str]], Optional) -> None
        """Load a configuration file

        If a system_type is supplied, such as "gateway", "client", or "engine",
        configuration options for that specific system type override options
        in the [DEFAULT] section. Similarly, if a host name is supplied, the
        options under the section of that specific host name override other
        options.

        The parameters after system_type and host_name are passed directly to
        ConfigParser.read().

        :param system_type: the type of the system to read configuration for
        :param host_name: the host name of the system
        :param default: a SectionProxy or any dict-like object that provides
                        default values
        """
        super(ConfigFile, self).__init__(logger, system_type, host_name, default)
        # Parent's init should've loaded the default values in.
        cp = ConfigParser(defaults=self._config)
        self.loaded_files = cp.read(filenames)
        self.log(logging.INFO, 'Loaded config files: ' + str(self.loaded_files))
        # We use the [system_type] section in our config file to overwrite the default values.
        self._config = cp
        if system_type:
            if system_type in self._config.sections():
                self._config['DEFAULT'].update(self._config[system_type])
            if host_name and system_type + '.' + host_name in self._config.sections():
                self._config = self._config[system_type + '.' + host_name]
            else:
                self._config = self._config['DEFAULT']
        else:
            self._config = self._config['DEFAULT']

    @overrides(ConfigBase)
    def get_config(self):
        return self._config
