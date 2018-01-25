"""ConfigBase of TuneUp.ai Client
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

import abc


class ConfigBase(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, logger):
        self._logger = logger
        pass

    @abc.abstractmethod
    def get_config(self):
        """Return a dict-like object for accessing the configuration values

        You should use the more specific methods from this class for accessing
        the configuration if they exist. Use this dict for low-level access
        only.
        """
        pass

    @abc.abstractmethod
    def db_type(self):
        """Return the type of database as instructed by the config
        :return: type of database
        """
        pass

    @abc.abstractmethod
    def db_path(self):
        """Return the path of DB as instructed by the config
        :return: path to access the database
        """
        pass
