# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup


setup(
    name='requirements-tools',
    description='Scripts for working with Python requirements.',
    version='2.0.0',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    install_requires=[
        'pytest',
        # RequirementParseError got refactored in v49
        # (https://github.com/pypa/setuptools/blob/main/CHANGES.rst#changes-20])
        # and doesn't appear to be entirely backwards compatible.
        'setuptools>18.5,<49',
        'virtualenv',
    ],
    packages=find_packages(exclude=('tests*',)),
    entry_points={
        'console_scripts': [
            'check-all-wheels = requirements_tools.check_all_wheels:main',
            'check-requirements = requirements_tools.check_requirements:main',
            'upgrade-requirements = requirements_tools.upgrade_requirements:main',  # noqa
            'visualize-requirements = requirements_tools.visualize_requirements:main',  # noqa
        ],
    },
)
