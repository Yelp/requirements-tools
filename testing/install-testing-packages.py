#!/usr/bin/env python
import os.path
import subprocess
import sys


ALL_PACKAGES = (
    'depends-on-prerelease-pkg',
    'prerelease-pkg',
)


def main():
    for pkg in ALL_PACKAGES:
        with open(os.devnull, 'w') as devnull:
            subprocess.call(
                (sys.executable, '-m', 'pip', 'uninstall', '-y', pkg),
                stdout=devnull,
                stderr=devnull,
            )
        subprocess.check_output((
            sys.executable, '-m', 'pip', 'install',
            # We'll manage dependencies manually
            '--no-deps',
            os.path.join('testing', pkg),
        ))


if __name__ == '__main__':
    exit(main())
