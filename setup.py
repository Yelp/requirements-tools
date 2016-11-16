# -*- coding: utf-8 -*-
from setuptools import setup


setup(
    name='check_requirements',
    description='Console script to help with testing requirements.',
    version='0.7.5',
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
    install_requires=['pytest'],
    py_modules=['check_requirements'],
    entry_points={
        'console_scripts': [
            'check-requirements = check_requirements:main',
        ],
    },
)
