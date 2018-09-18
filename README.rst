Introduction
============

This is the TuneUp.ai Client.

* `_tuclient_daemon.sh` is the main script of the TUClient daemon.
* `tuclient_daemon.sh` is used to start `_tuclient_daemon.sh` as a
  service. This is useful for development and debugging. For
  production, you should use a system-provided mechanism, such as
  systemd, to start `_tuclient_daemon.sh` as a service.

Supported platforms
===================

We'd like to have TuneUp.ai Client support all platforms that could
run Python (version 2.7 and up).

Currently, the following OSes are fully supported:

* CentOS 7

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
