#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_intel-nfv-ci-tests
----------------------------------

Tests for `intel_nfv_ci_tests` module.
"""

import unittest

from intel_nfv_ci_tests import intel_nfv_ci_tests


class TestIntel_nfv_ci_tests(unittest.TestCase):

    def setUp(self):
        dummy = intel_nfv_ci_tests
        repr(dummy)

    def test_something(self):
        pass

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
