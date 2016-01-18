#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015 Intel Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

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
