#!/usr/bin/env python
"""Unit tests for the common getter"""
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

from configparser import ConfigParser
import filecmp
import logging
import os
from shutil import copyfile
import sys
from threading import Thread
import time
import tuclient
from tuclient import ClientStatus, monotonic_time, run_shell_command
from tuclient_extensions import common_getters, normalize_from_range
from tuclient_tests import MockTUGateway
import unittest
from uuid import uuid1


class TestCommonGetter(unittest.TestCase):
    def setUp(self):
        self._logger = tuclient.get_stdout_logger()
        # We don't want to display the warnings of fifo not exist
        self._logger.setLevel(logging.ERROR)
        self._tuclient_config = tuclient.ConfigFile(None, 'client', None,
                                                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                 'test_common_getter.conf', ))

    def _write_to_fifo(self, file_name, s):
        if self._file_writer_obj is None:
            # Open it as line-buffered (you can't open a text file as unbuffered)
            self._file_writer_obj = open(file_name, 'wt', buffering=1)
        self._file_writer_obj.write(s)
        self._file_writer_obj.flush()

    def _collect_from_getter(self, getter, interval, requested_time):
        self._collected_data = getter.collect(interval, requested_time)

    def test_start_stop(self):
        getter = common_getters.Getter(self._logger, 'host1', self._tuclient_config)
        self.assertListEqual(['host1/wrk_completed_requests'], getter.pi_names)

        fifo_name = '/tmp/test_common_getter.fifo'
        if os.path.exists(fifo_name):
            os.remove(fifo_name)
        # The fifo doesn't exist yet, so collect() should return an empty list.
        self.assertListEqual([], getter.collect(3, 0))
        os.mkfifo(fifo_name)
        # Because opening and writing to a fifo will block, we need to open a thread
        # to do them.
        self._file_writer_obj = None
        Thread(target=self._write_to_fifo, args=(fifo_name, '0,0\n')).start()
        # Make sure data is written to the fifo
        time.sleep(0.5)
        self.assertListEqual([-1], getter.collect(3, 0))

        # This read should time out after 3 seconds
        self.assertListEqual([], getter.collect(3, 3))

        # Now we switch the order of collect() and write()
        t = Thread(target=self._collect_from_getter, args=(getter, 3, 3))
        t.start()
        # Make sure the reader is started
        time.sleep(0.5)
        self._write_to_fifo(fifo_name, '3,1500000\n')
        t.join()
        self.assertListEqual([1], self._collected_data)

        # Test if the reader can handle a close pipe event correctly
        self._file_writer_obj.close()
        self._file_writer_obj = None
        t = Thread(target=self._collect_from_getter, args=(getter, 3, 6))
        t.start()
        # Make sure the reader is started
        time.sleep(0.5)
        self._write_to_fifo(fifo_name, '6,750000\n')
        t.join()
        self.assertListEqual([0], self._collected_data)

        # Testing closing the pipe after reading is started
        t = Thread(target=self._collect_from_getter, args=(getter, 3, 9))
        t.start()
        # Make sure the reader is started
        time.sleep(0.5)
        self._file_writer_obj.close()
        self._file_writer_obj = None
        self._write_to_fifo(fifo_name, '9,0\n')
        t.join()
        self.assertListEqual([-1], self._collected_data)

        # Testing closing and reopening the pipe before reading is started
        self._file_writer_obj.close()
        # Reopen the writer before starting the reader
        self._file_writer_obj = open(fifo_name, 'wt', 1)
        t = Thread(target=self._collect_from_getter, args=(getter, 3, 12))
        t.start()
        # Make sure the reader is started
        time.sleep(0.5)
        self._write_to_fifo(fifo_name, '12,750000\n')
        # Second collect should get the correct data
        t.join()
        self.assertListEqual([0], self._collected_data)

        getter.stop()
        self._file_writer_obj.close()

    def test_normalize_from_range(self):
        self.assertEqual(0.5, normalize_from_range(1, 5, 4))
        self.assertEqual(-0.5, normalize_from_range(1, 5, 2))
        self.assertEqual(-1, normalize_from_range(1, 5, 1))
        self.assertEqual(1, normalize_from_range(1, 5, 5))


if __name__ == '__main__':
    unittest.main()
