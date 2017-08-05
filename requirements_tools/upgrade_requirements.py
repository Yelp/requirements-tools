#!/usr/bin/env python
import argparse
import contextlib
import os
import pipes
import shutil
import subprocess
import sys
import tempfile

from pkg_resources import Requirement
from pkg_resources import working_set


installed_things = {pkg.key: pkg for pkg in working_set}

reqs_filename = 'requirements.txt'
reqs_dev_filename = 'requirements-dev.txt'
reqs_minimal_filename = 'requirements-minimal.txt'
reqs_vcs_filename = 'requirements-vcs.txt'
reqs_dev_minimal_filename = 'requirements-dev-minimal.txt'
reqs_dev_vcs_filename = 'requirements-dev-vcs.txt'


class NeedsMoreInstalledError(RuntimeError):
    pass


def color(s, color):
    if sys.stdout.isatty():
        return '{}{}{}'.format(color, s, '\033[m')
    else:
        return s


def fmt_cmd(cmd):
    ret = '>>> {}'.format(' '.join(pipes.quote(x) for x in cmd))
    return color(ret, '\033[32m')


def print_call(*cmd, **kwargs):
    print(fmt_cmd(cmd))
    subprocess.check_call(cmd, **kwargs)


def reexec(*cmd, **kwargs):
    reason = kwargs.pop('reason')
    assert not kwargs, kwargs
    print(color('*** exec-ing: {}'.format(reason), '\033[33m'))
    print(fmt_cmd(cmd))
    # Never returns
    os.execv(cmd[0], cmd)


def requirements(requirements_filename, vcs=False):
    with open(requirements_filename) as requirements_file:
        for line in requirements_file:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            vcs_prefixes = ('-e', 'git:', 'git+', 'hg+', 'svn+', 'bzr+')
            if not vcs and line.startswith(vcs_prefixes):
                continue
            if vcs and not line.startswith(vcs_prefixes):
                continue
            yield line


def installed(requirements_file):
    expected_pinned = set()
    requirements_to_parse = list([
        Requirement.parse(r)
        for r in requirements(requirements_file)
    ])
    already_parsed = {(req.key, req.extras) for req in requirements_to_parse}
    unmet = set()

    while requirements_to_parse:
        req = requirements_to_parse.pop()
        installed_req = installed_things[req.key]
        expected_pinned.add('{}=={}'.format(
            installed_req.project_name, installed_req.version,
        ))
        for sub in installed_req.requires(req.extras):
            if sub.key not in installed_things:
                specifiers = ','.join(str(s) for s in sub.specifier)
                unmet.add('{}{}'.format(sub.key, specifiers))
            elif (sub.key, sub.extras) not in already_parsed:
                requirements_to_parse.append(sub)
                already_parsed.add((sub.key, sub.extras))

    if unmet:
        raise NeedsMoreInstalledError(unmet)
    else:
        return expected_pinned


def dirs(tmp):
    dirnames = ('venv', 'venv/bin/python', 'venv/bin/pip')
    return tuple(os.path.join(tmp, d) for d in dirnames)


@contextlib.contextmanager
def cleanup_dir(dirname):
    try:
        yield dirname
    finally:
        shutil.rmtree(dirname)


def file_exists(path):
    return os.path.exists(path) and os.path.isfile(path)


def make_virtualenv(args):
    with cleanup_dir(tempfile.mkdtemp()) as tempdir:
        venv, python, pip = dirs(tempdir)
        print_call(
            sys.executable, '-m', 'virtualenv', venv,
            '-p', args.python, '--never-download',
        )

        def pip_install(*argv):
            print_call(pip, 'install', '-i', args.index_url, *argv)

        # Latest pip installs python3.5 wheels
        pip_install('pip', 'setuptools', '--upgrade')
        pip_install('-r', reqs_minimal_filename)
        if file_exists(reqs_vcs_filename):
            pip_install('-r', reqs_vcs_filename)
        if file_exists(reqs_dev_minimal_filename):
            pip_install('-r', reqs_dev_minimal_filename)
        if file_exists(reqs_dev_vcs_filename):
            pip_install('-r', reqs_dev_vcs_filename)

        reexec(
            python, __file__.rstrip('c'),
            '--tempdir', tempdir,
            # Pass along existing args
            '--index-url', args.index_url,
            '--exec-count', str(args.exec_count),
            '--exec-limit', str(args.exec_limit),
            reason='to use the virtualenv python',
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p', '--python',
        default='python' + '.'.join(str(x) for x in sys.version_info[:2]),
    )
    parser.add_argument(
        '-i', '--index-url', default='https://pypi.python.org/simple',
    )
    parser.add_argument(
        '--exec-limit', type=int, default=10, help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--exec-count', type=int, default=0, help=argparse.SUPPRESS,
    )
    parser.add_argument('--tempdir', help=argparse.SUPPRESS)
    args = parser.parse_args()

    assert file_exists(reqs_minimal_filename)

    if args.tempdir is None:
        make_virtualenv(args)  # Never returns

    venv, python, pip = dirs(args.tempdir)

    with cleanup_dir(args.tempdir):
        try:
            reqs = installed(reqs_minimal_filename)

            if file_exists(reqs_vcs_filename):
                reqs_git = set(requirements(reqs_vcs_filename, True))
            else:
                reqs_git = set()

            if file_exists(reqs_dev_minimal_filename):
                reqs_dev = installed(reqs_dev_minimal_filename)
            else:
                reqs_dev = set()

            if file_exists(reqs_dev_vcs_filename):
                reqs_dev_git = set(requirements(reqs_dev_vcs_filename, True))
            else:
                reqs_dev_git = set()

        except NeedsMoreInstalledError as e:
            print(color('Installing unmet requirements!', '\033[31m'))
            print('Probably due to https://github.com/pypa/pip/issues/3903')
            new_exec_count = args.exec_count + 1
            if new_exec_count > args.exec_limit:
                raise AssertionError('--exec-limit depth limit exceeded')
            unmet, = e.args
            print_call(pip, 'install', '-i', args.index_url, *unmet)
            reexec(
                python, __file__.rstrip('c'),
                '--exec-count', str(new_exec_count),
                # Pass along existing args
                '--index-url', args.index_url,
                '--tempdir', args.tempdir,
                '--exec-limit', str(args.exec_limit),
                reason='Unmet dependencies',
            )
        else:
            reqs_full = list(reqs) + list(reqs_git)
            with open(reqs_filename, 'w') as f:
                f.write('\n'.join(reqs_full) + '\n')

            create_reqs_dev = file_exists(
                reqs_dev_minimal_filename
            ) and file_exists(
                reqs_dev_vcs_filename
            )
            if create_reqs_dev:
                reqs_full_dev = list(reqs_dev - reqs) + \
                    list(reqs_dev_git - reqs_git)
                with open(reqs_dev_filename, 'w') as f:
                    f.write('\n'.join(reqs_full_dev) + '\n')

            with open(os.devnull, 'w') as devnull:
                subprocess.check_call(
                    (pip, 'install', 'pre-commit-hooks'),
                    stdout=devnull, stderr=devnull,
                )

            popenargs = (os.path.join(
                venv, 'bin', 'requirements-txt-fixer'), reqs_filename)
            if create_reqs_dev:
                popenargs = popenargs + (create_reqs_dev,)
            subprocess.call(popenargs)


if __name__ == '__main__':
    exit(main())
