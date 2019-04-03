%bcond_with snapshot

%if 0%{?fedora}
%if 0%{?fedora} > 27
%bcond_without python3
%else
%bcond_with python3
%endif
%else
%if 0%{?rhel} && 0%{?rhel} < 8
%bcond_with python3
%else
%bcond_without python3
%endif
%endif

%if %{with python3}
%global _py python3
%else
%{!?python2_sitelib:%global python2_sitelib %{python_sitelib}}
%if 0%{?rhel} && 0%{?rhel} < 8
%global _py python
%else
%global _py python2
%endif
%endif

%if %{with snapshot}
%if 0%{!?git_short_commit:1}
%global git_short_commit %(git rev-parse --short=8 --verify HEAD)
%endif
%global git_date %(date +'%Y%m%d')
%global git_suffix %{git_date}git%{git_short_commit}
%endif

#%%global prerelease rc
#%%global prereleasenum 1

%global prerel1 %{?prerelease:.%{prerelease}%{prereleasenum}}
%global prerel2 %{?prerelease:-%{prerelease}.%{prereleasenum}}

Summary: TuneUp.ai Client
Name: tuclient
Version: 0.3
Release: 1%{?prerel1}%{?with_snapshot:.%{git_suffix}}%{?dist}
License: LGPLv2.1
Source0: %{name}-%{?prerel2}/%{name}-%{version}%{?prerel2}.tar.gz
URL: https://tuneup.ai/
BuildArch: noarch
BuildRequires: systemd
Requires(post): systemd, virt-what
Requires(preun): systemd
Requires(postun): systemd
BuildRequires: %{_py}, %{_py}-devel
Requires: %{_py}-decorator, %{_py}-pyudev, %{_py}-configobj
Requires: %{_py}-schedutils, %{_py}-linux-procfs, %{_py}-perf
Requires: %{_py}-daemon, %{_py}-zmq, %{_py}-typing
# requires for packages with inconsistent python2/3 names
%if %{with python3}
Requires: python3-dbus, python3-gobject-base
%else
Requires: dbus-python, pygobject3-base, python-configparser, python-enum34
Requires: python-monotonic
%endif
Requires: virt-what, ethtool, gawk, hdparm
Requires: util-linux, dbus, polkit
%if 0%{?fedora} > 22 || 0%{?rhel} > 7
Recommends: kernel-tools
%endif

%description
TuneUp.ai Client contains a daemon that collects status information of the
system and tunes system settings dynamically. It does so by sending the
collected data to a TuneUp.ai Engine, which performance deep reinforcement
learning to generate new settings.

%if 0%{?rhel} <= 7 && 0%{!?fedora:1}
# RHEL <= 7
%global docdir %{_docdir}/%{name}-%{version}
%else
# RHEL > 7 || fedora
%global docdir %{_docdir}/%{name}
%endif

%prep
%setup -q -n %{name}-%{version}%{?prerel2}

%build

%install
make install DESTDIR=%{buildroot} DOCDIR=%{docdir} \
%if %{with python3}
	PYTHON=%{__python3}
%else
	PYTHON=%{__python}
%endif

%post
%systemd_post tuclient.service

%preun
%systemd_preun tuclient.service
if [ "$1" == 0 ]; then
# clear persistent storage
  rm -f %{_var}/lib/tuclient/*
# clear temporal storage
  rm -f /run/tuclient/*
fi


%postun
%systemd_postun_with_restart tuclient.service


%files
%defattr(-,root,root,-)
%doc %{docdir}
%if %{with python3}
%{python3_sitelib}/tuclient
%{python3_sitelib}/tuclient_extensions
%{python3_sitelib}/tuclient_tests
%else
%{python2_sitelib}/tuclient
%{python2_sitelib}/tuclient_extensions
%{python2_sitelib}/tuclient_tests
%endif
%{_sbindir}/lc
%{_sbindir}/tuclientd
%dir %{_sysconfdir}/tuclient
%config(noreplace) %{_sysconfdir}/tuclient/tuclient_daemon.conf
%{_unitdir}/tuclient.service
%dir %{_localstatedir}/log/tuclient
%dir /run/tuclient


%changelog
* Tue Mar 16 2019 Yan Li <yanli@tuneup.ai> 0.3-1
- upstream release

* Tue Sep 11 2018 Yan Li <yanli@tuneup.ai> 0.1-1
- first release
