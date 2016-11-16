#!/usr/bin/env python
import os.path
import subprocess
import sys


ALL_PACKAGES = (
    'depends-on-prerelease-pkg', 'prerelease-pkg',
    'pkg-with-deps', 'pkg-dep-1', 'pkg-dep-2',
    'other-pkg-with-deps', 'other-dep-1',
    'pkg-unmet-deps',
    'pkg-with-extras',
    'depends-on-pkg-with-extras',
)


def main():
    for pkg in ALL_PACKAGES:
        with open(os.devnull, 'w') as devnull:
            subprocess.call(
                (sys.executable, '-m', 'pip', 'uninstall', '-y', pkg),
                stdout=devnull,
                stderr=devnull,
            )
    subprocess.check_output(
        # We'll manage dependencies manually
        (sys.executable, '-m', 'pip', 'install', '--no-deps') +
        tuple(os.path.join('testing', pkg) for pkg in ALL_PACKAGES)
    )


if __name__ == '__main__':
    exit(main())
