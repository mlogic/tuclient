"""Mock TUClient Extension class"""
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
from typing import List
from tuclient import *

__author__ = 'Yan Li'
__copyright__ = 'CONFIDENTIAL. Copyright (c) 2017-2019 Yan Li. All rights reserved.'
__license__ = 'CONFIDENTIAL INFORMATION OF YAN LI'
__docformat__ = 'reStructuredText'


class Getter(GetterExtensionBase):
    @overrides(GetterExtensionBase)
    def collect(self):
        # type: () -> List[float]
        """Collect Performance Indicators"""
        return [1, 2]

    @property
    @overrides(GetterExtensionBase)
    def pi_names(self):
        return ['pi_a', 'pi_b']


class Setter(SetterExtensionBase):
    @overrides(SetterExtensionBase)
    def action(self, actions):
        # type: (List[float]) -> None
        """Perform actions
        :param actions: a list of actions to perform"""
        pass

    @property
    @overrides(SetterExtensionBase)
    def parameter_names(self):
        return ['param_a', 'param_b']
