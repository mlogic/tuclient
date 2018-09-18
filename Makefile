NAME = tuclient
# set to devel for nightly GIT snapshot
BUILD = release
# which config to use in mock-build target
MOCK_CONFIG = epel-7-x86_64
# scratch-build for triggering Jenkins
SCRATCH_BUILD_TARGET = rhel-7.5-candidate
VERSION = $(shell awk '/^Version:/ {print $$2}' tuclient.spec)
GIT_DATE = $(shell date +'%Y%m%d')
ifeq ($(BUILD), release)
	RPM_ARGS += --without snapshot
	MOCK_ARGS += --without=snapshot
	RPM_VERSION = $(NAME)-$(VERSION)-1
else
	RPM_ARGS += --with snapshot
	MOCK_ARGS += --with=snapshot
	GIT_SHORT_COMMIT = $(shell git rev-parse --short=8 --verify HEAD)
	GIT_SUFFIX = $(GIT_DATE)git$(GIT_SHORT_COMMIT)
	GIT_PSUFFIX = .$(GIT_SUFFIX)
	RPM_VERSION = $(NAME)-$(VERSION)-1$(GIT_PSUFFIX)
endif
UNITDIR_FALLBACK = /usr/lib/systemd/system
UNITDIR_DETECT = $(shell pkg-config systemd --variable systemdsystemunitdir || rpm --eval '%{_unitdir}' 2>/dev/null || echo $(UNITDIR_FALLBACK))
UNITDIR = $(UNITDIR_DETECT:%{_unitdir}=$(UNITDIR_FALLBACK))
TMPFILESDIR_FALLBACK = /usr/lib/tmpfiles.d
TMPFILESDIR_DETECT = $(shell pkg-config systemd --variable tmpfilesdir || rpm --eval '%{_tmpfilesdir}' 2>/dev/null || echo $(TMPFILESDIR_FALLBACK))
TMPFILESDIR = $(TMPFILESDIR_DETECT:%{_tmpfilesdir}=$(TMPFILESDIR_FALLBACK))
VERSIONED_NAME = $(NAME)-$(VERSION)$(GIT_PSUFFIX)

SYSCONFDIR = /etc
DATADIR = /usr/share
DOCDIR = $(DATADIR)/doc/$(NAME)
PYTHON = python
PYLINT = pylint-3
ifeq ($(PYTHON),python2)
PYLINT = pylint-2
endif
SHEBANG_REWRITE_REGEX= '1s|^\#!/usr/bin/\<python\>|\#!$(PYTHON)|'
PYTHON_SITELIB = $(shell $(PYTHON) -c 'from distutils.sysconfig import get_python_lib; print(get_python_lib());')
ifeq ($(PYTHON_SITELIB),)
$(error Failed to determine python library directory)
endif

copy_executable = install -Dm 0755 $(1) $(2)
rewrite_shebang = sed -i -r -e $(SHEBANG_REWRITE_REGEX) $(1)
restore_timestamp = touch -r $(1) $(2)
install_python_script = $(call copy_executable,$(1),$(2)) \
	&& $(call rewrite_shebang,$(2)) && $(call restore_timestamp,$(1),$(2));

release-dir:
	mkdir -p $(VERSIONED_NAME)

release-cp: release-dir
	cp -a AUTHORS COPYING README.rst $(VERSIONED_NAME)

	cp -a tuclientd.py tuclient.spec tuclient.service Makefile setup.py \
		tuclient_daemon.sh $(VERSIONED_NAME)

	cp -a tuclient tuclient_extensions tuclient_tests \
		$(VERSIONED_NAME)

archive: clean release-cp
	tar czf $(VERSIONED_NAME).tar.gz $(VERSIONED_NAME)

rpm-build-dir:
	mkdir rpm-build-dir

srpm: archive rpm-build-dir
	rpmbuild --define "_sourcedir `pwd`/rpm-build-dir" --define "_srcrpmdir `pwd`/rpm-build-dir" \
		--define "_specdir `pwd`/rpm-build-dir" --nodeps $(RPM_ARGS) -ts $(VERSIONED_NAME).tar.gz

rpm: archive rpm-build-dir
	rpmbuild --define "_sourcedir `pwd`/rpm-build-dir" --define "_srcrpmdir `pwd`/rpm-build-dir" \
		--define "_specdir `pwd`/rpm-build-dir" --nodeps $(RPM_ARGS) -tb $(VERSIONED_NAME).tar.gz

clean-mock-result-dir:
	rm -f mock-result-dir/*

mock-result-dir:
	mkdir mock-result-dir

mock-build: srpm
	mock -r $(MOCK_CONFIG) $(MOCK_ARGS) --resultdir=`pwd`/mock-result-dir `ls rpm-build-dir/*$(RPM_VERSION).*.src.rpm | head -n 1`&& \
	rm -f mock-result-dir/*.log

mock-devel-build: srpm
	mock -r $(MOCK_CONFIG) --with=snapshot \
		--define "git_short_commit `if [ -n \"$(GIT_SHORT_COMMIT)\" ]; then echo $(GIT_SHORT_COMMIT); else git rev-parse --short=8 --verify HEAD; fi`" \
		--resultdir=`pwd`/mock-result-dir `ls rpm-build-dir/*$(RPM_VERSION).*.src.rpm | head -n 1` && \
	rm -f mock-result-dir/*.log

install-dirs:
	mkdir -p $(DESTDIR)$(PYTHON_SITELIB)
	mkdir -p $(DESTDIR)/var/log/tuclient
	mkdir -p $(DESTDIR)/run/tuclient
	mkdir -p $(DESTDIR)$(DOCDIR)
	mkdir -p $(DESTDIR)$(SYSCONFDIR)

install: install-dirs
	# library
	cp -a tuclient $(DESTDIR)$(PYTHON_SITELIB)

	# binaries
	$(call install_python_script,tuclientd.py,$(DESTDIR)/usr/sbin/tuclientd)

	# configuration files
	install -Dpm 0644 tuclient/default_conf_file.ini $(DESTDIR)$(SYSCONFDIR)/tuclient/tuclient.conf

	# systemd units
	install -Dpm 0644 tuclient.service $(DESTDIR)$(UNITDIR)/tuclient.service

	# documentation
	cp AUTHORS COPYING README.rst $(DESTDIR)$(DOCDIR)

clean:
	find -name "*.pyc" | xargs rm -f
	rm -rf $(VERSIONED_NAME) rpm-build-dir

test:
	$(PYTHON) -m unittest discover tuclient_tests
	tuclient_tests/test_tuclient_daemon.sh

func-test: test

lint:
	$(PYLINT) -E -f parseable tuclient *.py

.PHONY: archive clean clean-mock-result-dir func-test install install-dirs lint \
        mock-build mock-devel-build mock-result-dir rpm rpm-build-dir srpm \
        tag test
