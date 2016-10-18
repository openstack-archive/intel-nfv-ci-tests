==================
intel-nfv-ci-tests
==================

A Tempest plugin providing integration tests for NFV features.

This plugin is run as part of the
`Intel NFV third-party CI <https://wiki.openstack.org/wiki/ThirdPartySystems/Intel_NFV_CI>`_.

Features
--------

The tests validate the following features:

* NUMA topologies
* CPU pinning
* Hugepages

Requirements
------------

The features tested are all dependent on underlying hardware support. As such,
the following platform features are required:

* Simultaneous multithreading (SMT) technology, e.g. Hyper-threading, must be
  available and enabled
* A NUMA topology is required. This will generally mean a dual-socket board or
  a CPU with Cluster-on-Die technology
* Hugepages must be supported

Installation
------------

The plugin should be installed like any other package. Once installed, it will
be detected on subsequent runs of Temptest and enabled by default.

At the command line, run::

    $ pip install intel-nfv-ci-tests

Or, if you have virtualenvwrapper installed, run::

    $ mkvirtualenv intel-nfv-ci-tests
    $ pip install intel-nfv-ci-tests

Be aware that this package will not be available if running Tempest in a
different virtualenv, e.g. via a Tox target.

Usage
-----

All test commands should be run from the Tempest install directory, e.g.
``/opt/stack/tempest``.

To list all Intel NFV CI tempest cases, run::

    $ testr list-tests intel_nfv_ci_tests

To run only these tests, run::

    $ ./run_tempest.sh -N -- intel_nfv_ci_tests

Alternatively, run via ``testr``::

    $ testr run intel_nfv_ci_tests

Or via tox::

    $ tox -e all-plugin intel_nfv_ci_tests

To run a single test case, run with test case name::

    $ ./run_tempest.sh -N -- intel_nfv_ci_tests.tests.scenario.test_hugepages.TestHugepages
