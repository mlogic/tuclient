#!/usr/bin/env python
"""Set up script for TuneUp.ai Client"""

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

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import sys

setup_requires = [
          'pyzmq',
          'python-daemon',
          'Sphinx',
          'sphinx_rtd_theme',
      ]
if sys.version_info[0] < 3:
    setup_requires += ['enum','typing']

setup(name='tuclient',
      version='0.1',
      packages=[],
      setup_requires=setup_requires,
      # Metadata for PyPI
      author='Yan Li',
      author_email='yanli@tuneup.ai',
      description='TuneUp.ai Client',
      license='LGPLv2.1',
      url='https://tuneup.ai',
      )
