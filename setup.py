# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup


setup(
    name='pytest_requirements_checks',
    description='pytest plugin to check common mistakes with versioning',
    version='0.0.0',
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    install_requires=['pytest', 'simplejson'],
    packages=find_packages('.', exclude=('tests*', 'testing*')),
    entry_points={
        'pytest11': [
            'pytest-requirements-checks = pytest_requirements_checks.plugin',
        ],
    },
)
