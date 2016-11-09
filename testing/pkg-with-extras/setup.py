from setuptools import setup

setup(
    name='pkg-with-extras',
    version='0.1.0',
    extras_require={'extra': ['pkg-dep-1']},
)
