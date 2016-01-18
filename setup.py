#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read().replace('.. :changelog:', '')

requirements = [
    # TODO(requirements): put package requirements here
]

test_requirements = [
    # TODO(test-requirements): put package test requirements here
]

setup(
    name='intel_nfv_ci_tests',
    version='0.1.0',
    description="Repository containing tests for Intel NFV 3rd party CI",
    long_description=readme + '\n\n' + history,
    author="Waldemar Znoinski",
    author_email='waldemar.znoinski@intel.com',
    url='https://github.com/openstack/intel-nfv-ci-tests',
    packages=[
        'intel_nfv_ci_tests',
    ],
    package_dir={'intel_nfv_ci_tests':
                 'intel_nfv_ci_tests'},
    include_package_data=True,
    install_requires=requirements,
    license="Apache",
    zip_safe=False,
    keywords='intel_nfv_ci_tests',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
