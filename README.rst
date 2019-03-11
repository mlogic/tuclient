Introduction
============

This is the TuneUp.ai Client.

The client is usually installed as a system service, and you should
use your system's service control mechanism to start and stop the
client. For development or testing, you could use
``tuclient_daemon.sh`` to start an instance of the client.

Supported platforms
===================

We'd like to have TuneUp.ai Client support all platforms that could
run Python (version 2.7 and up).

Currently, the following OSes are fully supported:

* CentOS 7
* Ubuntu 18.04 LTS, 18.10

TuneUp.ai Client should also run on most Linux/Unix systems, prehaps
with minor changes. If you manage to make it run on systems other than
those listed above, we'd like to know. And patches are also welcome!

Installation instructions
=========================
For installation, run ``make install``. Optionally DESTDIR can be
appended.  By default, the ``python`` command as designated by
``PATH`` is used and the modules are installed to the python-lib
directory (e.g. /usr/lib/python3.6/site-packages/) and shebangs in
executable Python files are modified accordingly. This works well with
virtualenvs. If you want tuned to use another Python, use ``make
PYTHON=python_binary install``.

``python setup.py {sdist|bdist}`` is also supported if you need to
build Python source or binary packages.
