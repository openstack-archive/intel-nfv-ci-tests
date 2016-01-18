=====
Usage
=====

To list all Intel NFV CI tempest cases, go to tempest directory, then run::

    $ testr list-tests intel_nfv_ci_tests

To run only these tests in tempest, go to tempest directory, then run::

    $ ./run_tempest.sh -N -- intel_nfv_ci_tests

You can also run them using ``testr``::

    $ testr run intel_nfv_ci_tests

To run a single test case, go to tempest directory, then run with test case name, e.g.::

    $ ./run_tempest.sh -N -- intel_nfv_ci_tests.tests.scenario.test_hugepages.TestHugepages

Alternatively, to run Intel NFV CI tempest plugin tests using tox, go to tempest directory, then run::

    $ tox -eall-plugin intel_nfv_ci_tests
