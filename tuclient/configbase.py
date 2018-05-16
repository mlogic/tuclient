"""ConfigBase of TuneUp.ai Client"""
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
from typing import Any, Optional

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2018 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import abc
from configparser import ConfigParser
import logging
import os
from .tulogging import get_file_logger


class ConfigBase(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, logger=None, system_type=None, host_name=None):
        # type: (Optional[logging.Logger], Optional[str], Optional[str]) -> None
        """Initialize a ConfigBase object

        If a system_type is supplied, such as "gateway", "client", or "engine",
        configuration options for that specific system type override options
        in the [general] section. Similarly, if a host name is supplied, the
        options under the section of that specific host name override other
        options.

        A derivative class usually only needs to implement get_config().

        :param logger: a logger for logging config parsing-related information,
                       None can be passed to disable logging.
        :param system_type: the type of the system to read configuration for
        :param host_name: the host name of the system
        """
        self._logger = logger
        self._system_type = system_type
        self._host_name = host_name

        # Load default values
        cp = ConfigParser()
        default_config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'default_conf_file.ini')
        loaded_files = cp.read(default_config_file)
        if len(loaded_files) == 0:
            self.log(logging.WARNING, 'Failed to load default config file: ' + default_config_file)
            self._config = None
        else:
            self.log(logging.DEBUG, 'Loaded default config file ' + str(loaded_files))
            self._config = cp.defaults()

    @abc.abstractmethod
    def get_config(self):
        """Return a dict-like object for accessing the configuration values

        You should use the more specific methods from this class for accessing
        the configuration if they exist. Use this dict for low-level access
        only.
        """
        pass

    def node_name(self):
        # type: () -> str
        """Return the node name of the client
        :return: node name"""
        return self.get_config()['node_name']

    def api_secret_key(self):
        # type: () -> str
        """Return the API Secret Key of the client
        :return: API Secret Key"""
        return self.get_config()['api_secret_key']

    def cluster_name(self):
        # type: () -> str
        """Return the name of the cluster this client belongs to
        :return: the name of the cluster this client belongs to"""
        return self.get_config()['cluster_name']

    def daemon_output_dir(self):
        # type: () -> str
        """Return the location for storing daemons' stdout and stderr"""
        return self.get_config()['daemon_output_dir']

    def db_type(self):
        # type: () -> str
        """Return the type of database as instructed by the config
        :return: type of database
        """
        dbstr = self.get_config()['db']
        colon_pos = dbstr.index(':')
        return dbstr[:colon_pos]

    def db_path(self):
        # type: () -> str
        """Return the path of DB as instructed by the config
        :return: path to access the database
        """
        dbstr = self.get_config()['db']
        colon_pos = dbstr.index(':')
        return dbstr[colon_pos+1:]

    def gateway_address(self):
        # type: () -> str
        """Get the gateway address
        :return: gateway address"""
        return self.get_config()['gateway_address']

    def get_logger(self):
        # type: () -> logging.Logger
        """Get a logger as instructed by the config
        :return: the logger
        """
        logger = get_file_logger(self.log_file())
        logger.setLevel(self.logging_level())
        return logger

    def log_file(self):
        # type: () -> str
        """Return the path to the log file

        For most cases you should use get_logger() instead.

        :return: name of the log file
        """
        return self.get_config()['log_file']

    def logging_level(self):
        # type: () -> int
        """Return the logging level as instructed by the config

        For most cases you should use get_logger() instead.

        :return: logging level
        """
        levelstr = self.get_config()['logging_level'].upper()
        return logging._nameToLevel[levelstr]

    def log(self, level, message, *args, **kwargs):
        # type: (int, str, *Any, **Any) -> None
        """Write log message at level"""
        if self._logger:
            self._logger.log(level, message, *args, **kwargs)

    def protocol(self):
        # type: () -> str
        """Get the protocol name

        :return: protocol name"""
        return self.get_config()['protocol']

    def getter_module(self):
        # type: () -> str
        """Get the getter module name

        :return: getter module name"""
        return self.get_config()['getter_module']

    def setter_module(self):
        # type: () -> str
        """Get the setter module name

        :return: setter module name"""
        return self.get_config()['setter_module']

    def pidfile(self):
        # type: () -> str
        """Get the location for storing PID file
        :return: path for storing the PID files"""
        return self.get_config()['pidfile']

    def tick_len(self):
        # type: () -> int
        """Get the duration of a tick in seconds
        :return tick length in sections"""
        return self.get_config()['tick_len']
