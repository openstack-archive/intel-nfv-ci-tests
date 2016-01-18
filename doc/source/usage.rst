=====
Usage
=====

To validate that Tempest discovered the test in the plugin, you can run::

    $ testr list-tests | grep intel_nfv_ci_tests

This command should list all tests provided by the plugin.

You can then run them using ``testr``::

    testr run intel_nfv_ci_tests
