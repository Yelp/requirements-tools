# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup


setup(
    name='requirements_checks',
    description='Console script to help with testing requirements.',
    version='0.0.0',
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
    install_requires=['pytest', 'simplejson'],
    packages=find_packages('.', exclude=('tests*', 'testing*')),
    entry_points={
        'console_scripts': [
            'check-requirements = requirements_checks.main:main',
        ],
    },
)
