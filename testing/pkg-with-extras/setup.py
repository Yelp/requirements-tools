from setuptools import setup

setup(
    name='pkg-with-extras',
    version='0.1.0',
    extras_require={
        'extra1': ['pkg-dep-1'],
        'extra2': ['pkg-dep-2'],
        'extrapre': ['prerelease-pkg'],
    },
)
