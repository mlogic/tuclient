"""Test cases for misc. setter functions"""
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


__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'


from tuclient_extensions.getter_setter_misc import *
import unittest


class TestSetterMisc(unittest.TestCase):
    # We used to test get_pids() by letting it retrieve the PID of "sbin/init",
    # but that didn't run inside our builder Docker container.
    def test_get_pids(self):
        self.assertTrue(os.getpid() in get_pids('python'))

    def test_get_proc_cmdline(self):
        self.assertTrue('python' in get_proc_cmdline(os.getpid()))


if __name__ == '__main__':
    unittest.main()
