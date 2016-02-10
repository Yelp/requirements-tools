# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup


setup(
    name='check_requirements',
    description='Console script to help with testing requirements.',
    version='0.2.1',
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
    install_requires=['pytest'],
    packages=find_packages('.', exclude=('tests*', 'testing*')),
    entry_points={
        'console_scripts': [
            'check-requirements = check_requirements.main:main',
        ],
    },
)
