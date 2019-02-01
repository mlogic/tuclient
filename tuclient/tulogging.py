"""Helper functions for getting the singleton root logger
"""
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
#
# May contain source code from the UCSC CAPES Project:
# Copyright (c) 2016-2017 The Regents of the University of California. All
# rights reserved.
#
# Created by Yan Li <yanli@tuneup.ai>, Kenneth Chang <kchang44@ucsc.edu>,
# Oceane Bel <obel@ucsc.edu>. Storage Systems Research Center, Baskin School
# of Engineering.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Storage Systems Research Center, the
#       University of California, nor the names of its contributors
#       may be used to endorse or promote products derived from this
#       software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# REGENTS OF THE UNIVERSITY OF CALIFORNIA BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
# OF THE POSSIBILITY OF SUCH DAMAGE.
from __future__ import absolute_import, division, print_function, unicode_literals
from typing import Any, Optional

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import atexit
import io
import logging
import logging.handlers
import os
import socket
import sys

_STDOUT_LOGGER = 1
_FILE_LOGGER = 2
_MEMORY_LOGGER = 3

DEFAULT_FORMAT = '%(asctime)s - {name} - %(filename)s:%(lineno)s - %(funcName)10s() - %(message)s'
_log_file_handler = None
_memory_handler = None
memory_logger_stringios = dict()


def _logger_hasHandlers(logger):
    """Function copied from Python 3.6 for Python 2.7 or lower
    """
    if sys.version_info[0] >= 3:
        return logger.hasHandlers()

    c = logger
    rv = False
    while c:
        if c.handlers:
            rv = True
            break
        if not c.propagate:
            break
        else:
            c = c.parent
    return rv


def _get_stream_logger(name, stream):
    """Get a stream logger"""
    logger = logging.getLogger(name)
    if not _logger_hasHandlers(logger):
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT.format(name=name)))
        logger.addHandler(stream_handler)
        logger.setLevel(logging.WARNING)

    return logger


def get_console_logger(name=socket.gethostname()):
    """Get a logger that logs to stderr

    The returned logger will have name "console", and multiple calls return the same
    logger. Default log level is WARNING.
    """
    return _get_stream_logger(name, sys.stderr)


def get_stdout_logger(name=socket.gethostname()):
    """Get a logger that logs to stdou

    The returned logger will have name "stdout", and multiple calls return the same
    logger. Default log level is WARNING.
    """
    return _get_stream_logger(name, sys.stdout)


def flush_log():
    if _memory_handler is not None:
        _memory_handler.flush()


def get_file_logger(filename, lazy_flush=False, name=socket.gethostname()):
    """Create and return the root logger with a memory-cached file handler

    On first call, the root file logger is created, and the log level is set to WARN. On following calls, the
    root logger is returned (filename will be ignored), and the log level won't be changed.

    Exception will be risen if the root logger wasn't created as a file logger.
    """
    logger = logging.getLogger(name)
    if not _logger_hasHandlers(logger):
        pathname = os.path.dirname(filename)
        if os.path.exists(pathname) and not os.path.isdir(pathname):
            raise FileNotFoundError('Not a valid path: \'{}\''.format(pathname))
        elif not os.path.isdir(pathname):
            os.mkdir(pathname)
        global _log_file_handler
        _log_file_handler = logging.FileHandler(filename)
        formatter = logging.Formatter(DEFAULT_FORMAT.format(name=name))
        _log_file_handler.setFormatter(formatter)

        global _memory_handler
        _memory_handler = logging.handlers.MemoryHandler(
            capacity=1024 * 100,
            flushLevel=logging.ERROR if lazy_flush else logging.DEBUG,
            target=_log_file_handler
        )

        logger.addHandler(_memory_handler)

        atexit.register(flush_log)
        logger.setLevel(logging.WARNING)

    return logger


def get_memory_logger(name=socket.gethostname()):
    """Get a logger and stores all messages in memory and writes to stderr

    This memory logger keeps everything in memory and can use a huge amount of memory. Use it
    for test cases only.

    Use tulogging.memory_logger_stringio.getvalue() to get the log so far."""
    logger = logging.getLogger(name)
    if not _logger_hasHandlers(logger):
        memory_logger_stringio = io.StringIO()
        streamhandler = logging.StreamHandler(memory_logger_stringio)
        formatter = logging.Formatter(DEFAULT_FORMAT.format(name=name))
        streamhandler.setFormatter(formatter)
        stderrhandler = logging.StreamHandler()
        stderrhandler.setFormatter(formatter)
        logger.addHandler(streamhandler)
        logger.addHandler(stderrhandler)
        logger.setLevel(logging.WARNING)
        memory_logger_stringios[name] = memory_logger_stringio

    return logger


def logger_set_formatter(logger, format=None, name=socket.gethostname()):
    if format is None:
        format = DEFAULT_FORMAT.format(name=name)
    for handler in logger.handlers:
        handler.setFormatter(logging.Formatter(format))
