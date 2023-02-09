#!/usr/bin/env python
from __future__ import annotations

import argparse
import contextlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Generator
from typing import NoReturn
from typing import Sequence

from pkg_resources import Requirement
from pkg_resources import working_set


installed_things = {pkg.key: pkg for pkg in working_set}


class NeedsMoreInstalledError(RuntimeError):
    pass


def color(s: str, color: str) -> str:
    if sys.stdout.isatty():
        return '{}{}{}'.format(color, s, '\033[m')
    else:
        return s


def fmt_cmd(cmd: Sequence[str]) -> str:
    ret = '>>> {}'.format(' '.join(shlex.quote(x) for x in cmd))
    return color(ret, '\033[32m')


def print_call(*cmd: str) -> None:
    print(fmt_cmd(cmd))
    subprocess.check_call(cmd)


def reexec(*cmd: str, **kwargs: str) -> NoReturn:
    reason = kwargs.pop('reason')
    assert not kwargs, kwargs
    print(color(f'*** exec-ing: {reason}', '\033[33m'))
    print(fmt_cmd(cmd))
    # Never returns
    os.execv(cmd[0], cmd)


def requirements(
        requirements_filename: str,
) -> Generator[Requirement, None, None]:
    with open(requirements_filename) as requirements_file:
        for line in requirements_file:
            if line.strip() and not line.startswith(('#', '-e')):
                yield Requirement.parse(line.strip())


def installed(requirements_file: str) -> set[str]:
    expected_pinned = set()
    requirements_to_parse = list(requirements(requirements_file))
    already_parsed = {(req.key, req.extras) for req in requirements_to_parse}
    unmet = set()

    while requirements_to_parse:
        req = requirements_to_parse.pop()
        installed_req = installed_things[req.key]
        expected_pinned.add(
            f'{installed_req.project_name}=={installed_req.version}',
        )
        for sub in installed_req.requires(req.extras):
            if sub.key not in installed_things:
                specifiers = ','.join(
                    str(s) for s in sub.specifier  # type: ignore[attr-defined]
                )
                unmet.add(f'{sub.key}{specifiers}')
            elif (sub.key, sub.extras) not in already_parsed:
                requirements_to_parse.append(sub)
                already_parsed.add((sub.key, sub.extras))

    if unmet:
        raise NeedsMoreInstalledError(unmet)
    else:
        return expected_pinned


def venv_paths(tmp: str, pip_tool: str) -> tuple[str, ...]:
    dirnames = (
        'venv',
        'venv/bin/python',
        'venv/bin/pip',
        'venv/bin/' + pip_tool,
    )
    return tuple(os.path.join(tmp, d) for d in dirnames)


@contextlib.contextmanager
def cleanup_dir(dirname: str) -> Generator[str, None, None]:
    try:
        yield dirname
    finally:
        shutil.rmtree(dirname)


def make_virtualenv(args: argparse.Namespace) -> NoReturn:
    with cleanup_dir(tempfile.mkdtemp()) as tempdir:
        venv, python, pip, pip_tool_path = venv_paths(tempdir, args.pip_tool)
        pip_tool = tuple(shlex.split(pip_tool_path))

        print_call(
            sys.executable, '-m', 'virtualenv', venv,
            '-p', args.python, '--never-download',
        )

        def pip_install(pip: tuple[str, ...], *argv: str) -> None:
            install: tuple[str, ...] = ('install',)
            if args.index_url:
                install = ('install', '-i', args.index_url)
            print_call(*(pip + install + argv))

        # Latest pip installs python3.5 wheels
        pip_install(
            (pip,), '--upgrade', 'setuptools', 'pip',
        )
        pip_install((pip,), args.install_deps)
        pip_install(pip_tool, '-r', 'requirements-minimal.txt')
        pip_install(pip_tool, '-r', 'requirements-dev-minimal.txt')

        reexec_args = [
            python, __file__.rstrip('c'),
            '--tempdir', tempdir,
            # Pass along existing args
            '--exec-count', str(args.exec_count),
            '--exec-limit', str(args.exec_limit),
            '--pip-tool', args.pip_tool,
            f'--install-deps={args.install_deps}',
        ]

        if args.index_url:
            reexec_args.extend(('--index-url', args.index_url))

        reexec(*reexec_args, reason='to use the virtualenv python')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p', '--python',
        default='python' + '.'.join(str(x) for x in sys.version_info[:2]),
    )
    parser.add_argument('-i', '--index-url')
    parser.add_argument(
        '--exec-limit', type=int, default=10, help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--exec-count', type=int, default=0, help=argparse.SUPPRESS,
    )
    parser.add_argument('--tempdir', help=argparse.SUPPRESS)
    parser.add_argument('--pip-tool', default='pip')
    parser.add_argument('--install-deps', default='pip')
    args = parser.parse_args()

    assert os.path.exists('requirements-minimal.txt')
    assert os.path.exists('requirements-dev-minimal.txt')

    if args.tempdir is None:
        make_virtualenv(args)  # Never returns

    venv, python, pip, pip_tool_path = venv_paths(args.tempdir, args.pip_tool)
    pip_tool = tuple(shlex.split(pip_tool_path))

    with cleanup_dir(args.tempdir):
        try:
            reqs = installed('requirements-minimal.txt')
            reqs_dev = installed('requirements-dev-minimal.txt')
        except NeedsMoreInstalledError as e:
            print(color('Installing unmet requirements!', '\033[31m'))
            print('Probably due to https://github.com/pypa/pip/issues/3903')
            new_exec_count = args.exec_count + 1
            if new_exec_count > args.exec_limit:
                raise AssertionError('--exec-limit depth limit exceeded')
            unmet, = e.args

            install: tuple[str, ...] = ('install',)
            if args.index_url:
                install = ('install', '-i', args.index_url)
            print_call(*(pip_tool + install + tuple(unmet)))

            reexec_args = [
                python, __file__.rstrip('c'),
                '--exec-count', str(new_exec_count),
                # Pass along existing args
                '--tempdir', args.tempdir,
                '--exec-limit', str(args.exec_limit),
            ]

            if args.index_url:
                reexec_args.extend(('--index-url', args.index_url))

            reexec(*reexec_args, reason='Unmet dependencies')

        def _file_contents(reqs: set[str]) -> str:
            if not reqs:
                return ''
            else:
                return '\n'.join(reqs) + '\n'

        with open('requirements.txt', 'w') as f:
            f.write(_file_contents(reqs))
        with open('requirements-dev.txt', 'w') as f:
            f.write(_file_contents(reqs_dev - reqs))

        with open(os.devnull, 'w') as devnull:
            subprocess.check_call(
                pip_tool + ('install', 'pre-commit-hooks'),
                stdout=devnull, stderr=devnull,
            )
        subprocess.call((
            os.path.join(venv, 'bin', 'requirements-txt-fixer'),
            'requirements.txt', 'requirements-dev.txt',
        ))
    return 0


if __name__ == '__main__':
    exit(main())
