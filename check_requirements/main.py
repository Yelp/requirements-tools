from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import io
import json
import os.path
import subprocess
import sys
from operator import attrgetter

import pkg_resources
import pytest


installed_things = {pkg.key: pkg for pkg in pkg_resources.working_set}
REQUIREMENTS_FILES = frozenset(('requirements.txt', 'requirements-dev.txt'))


def get_lines_from_file(filename):
    with io.open(filename) as requirements_file:
        return [
            line.strip() for line in requirements_file
            if line.strip() and not line.startswith('#')
        ]


def get_raw_requirements(filename):
    lines = get_lines_from_file(filename)
    return [
        (pkg_resources.Requirement.parse(line), filename)
        for line in lines
        if not line.startswith('-e ')
    ]


def to_version(requirement):
    """Given a requirement spec, return the pinned version.

    Returns None if no single version is pinned.
    """
    if len(requirement.specs) != 1:
        return
    if requirement.specs[0][0] != '==':
        return
    return requirement.specs[0][1]


def to_equality_str(requirement):
    return '{}=={}'.format(requirement.key, to_version(requirement))


def to_pinned_versions(requirements):
    return {req.key: to_version(req) for req, _ in requirements}


def find_unpinned_requirements(requirements):
    """
    :param requirements: list of (requirement, filename)
    :return: Unpinned packages: list of
        (package_name, requiring_package, filename)
    """
    pinned_versions = to_pinned_versions(requirements)

    unpinned = {
        # unpinned packages already listed in requirements.txt
        (requirement.key, requirement, filename)
        for requirement, filename in requirements
        if not pinned_versions[requirement.key]
    }

    # unpinned packages which are needed but not listed in requirements.txt
    for requirement, filename in requirements:
        package_info = installed_things[requirement.key]

        for sub_requirement in package_info.requires(requirement.extras):

            if sub_requirement.key not in pinned_versions:
                unpinned.add(
                    (sub_requirement.key, requirement, filename)
                )

    return unpinned


def format_unpinned_requirements(unpinned_requirements):
    return '\t' + '\n\t'.join(
        '{} (required by {} in {})\n\t\tmaybe you want "{}"?'.format(
            package,
            requirement,
            filename,
            '{}=={}'.format(package, installed_things[package].version),
        )
        for package, requirement, filename in sorted(
            unpinned_requirements,
            key=str,
        )
    )


def test_requirements_pinned(requirements_files=REQUIREMENTS_FILES):
    # for compatibility with repos that haven't started using
    # requirements-dev-minimal.txt, we don't want to force pinning
    # requirements-dev.txt until they use minimal
    if not os.path.exists('requirements-dev-minimal.txt'):
        requirements_files -= {'requirements-dev.txt'}

    if all(
            not os.path.exists(reqfile)
            for reqfile in requirements_files
    ):  # pragma: no cover
        pytest.skip('No requirements files found')

    raw_requirements = sum(
        [
            get_raw_requirements(reqfile)
            for reqfile in requirements_files
            if os.path.exists(reqfile)
        ],
        [],
    )
    unpinned_requirements = find_unpinned_requirements(raw_requirements)
    if unpinned_requirements:
        raise AssertionError(
            'Unpinned requirements detected!\n\n{}'.format(
                format_unpinned_requirements(unpinned_requirements),
            )
        )


def get_package_name():
    return subprocess.check_output(
        (sys.executable, 'setup.py', '--name'),
    ).decode('UTF-8').strip()


def get_pinned_versions_from_requirement(requirement):
    expected_pinned = set()
    parsed = pkg_resources.Requirement.parse(requirement)
    requirements_to_parse = [parsed]
    while requirements_to_parse:
        req = requirements_to_parse.pop()
        installed_req = installed_things[req.key]
        for sub_requirement in installed_req.requires(req.extras):
            requirements_to_parse.append(sub_requirement)
            installed = installed_things[sub_requirement.key]
            expected_pinned.add(
                '{}=={}'.format(installed.key, installed.version)
            )
    return expected_pinned


def format_versions_on_lines_with_dashes(versions):
    return '\n'.join(
        '\t- {}'.format(req)
        for req in sorted(versions, key=attrgetter('key'))
    )


def test_top_level_dependencies():
    """Test that top-level requirements (setup.py and reqs-dev-minimal) are
    consistent with the pinned requirements.
    """
    if all(
            not os.path.exists(path) for path in (
                'setup.py',
                'requirements.txt',
                'requirements-dev-minimal.txt',
                'requirements-dev.txt',
            )
    ):  # pragma: no cover
        pytest.skip('No requirements files')

    package_name = get_package_name()

    expected_pinned_prod_deps = get_pinned_versions_from_requirement(
        package_name,
    )

    environments = [
        (
            expected_pinned_prod_deps,
            'requirements.txt',
            'setup.py',
        ),
    ]

    if os.path.exists('requirements-dev-minimal.txt'):
        expected_pinned_dev_deps = set()
        for req, _ in get_raw_requirements('requirements-dev-minimal.txt'):
            expected_pinned_dev_deps.add('{}=={}'.format(
                req.key,
                installed_things[req.key].version,
            ))
            expected_pinned_dev_deps |= get_pinned_versions_from_requirement(
                req.key,
            )
        # if there are overlapping prod/dev deps, only list in prod
        # requirements
        expected_pinned_dev_deps -= expected_pinned_prod_deps
        environments.append((
            expected_pinned_dev_deps,
            'requirements-dev.txt',
            'requirements-dev-minimal.txt',
        ))
    else:
        print(
            '\033[93;1m'
            'Warning: check-requirements is *not* checking your dev '
            'dependencies.\n'
            '\033[0m\033[93m'
            'To have your dev dependencies checked, create a file named\n'
            'requirements-dev-minimal.txt listing your minimal dev '
            'dependencies.\n'
            'See '
            'https://gitweb.yelpcorp.com/?p=python_packages/check_requirements.git;a=blob;f=README.md'  # noqa
            '\033[0m'
        )

    for expected_pinned, pin_filename, minimal_filename in environments:
        expected_pinned = {
            pkg_resources.Requirement.parse(s) for s in expected_pinned
        }
        if os.path.exists(pin_filename):
            requirements = {
                req for req, _ in get_raw_requirements(pin_filename)
            }
        else:
            requirements = set()

        pinned_but_not_required = requirements - expected_pinned
        required_but_not_pinned = expected_pinned - requirements

        if pinned_but_not_required:
            raise AssertionError(
                'Requirements are pinned in {pin} but are not depended '
                'on in {minimal}\n'
                '(Probably need to add something to {minimal})\n'
                '(or remove from {pin}):\n'
                '{}'.format(
                    format_versions_on_lines_with_dashes(
                        pinned_but_not_required,
                    ),
                    pin=pin_filename,
                    minimal=minimal_filename,
                )
            )

        if required_but_not_pinned:
            raise AssertionError(
                'Dependencies derived from {minimal} are not pinned in '
                '{pin}\n'
                '(Probably need to add something to {pin}):\n'
                '{}'.format(
                    format_versions_on_lines_with_dashes(
                        required_but_not_pinned,
                    ),
                    pin=pin_filename,
                    minimal=minimal_filename
                ),
            )


def test_no_underscores_all_dashes(requirements_files=REQUIREMENTS_FILES):
    if all(
            not os.path.exists(reqfile)
            for reqfile in requirements_files
    ):  # pragma: no cover
        pytest.skip('No requirements files found')

    for requirement_file in requirements_files:
        if not os.path.exists(requirement_file):
            continue
        for line in get_lines_from_file(requirement_file):
            if '_' in line:
                raise AssertionError(
                    'Use dashes for package names {}: {}'.format(
                        requirement_file, line,
                    )
                )


def test_bower_package_versions():
    if not os.path.exists('bower.json'):  # pragma: no cover
        pytest.skip('No bower.json file')
    bower_contents = json.loads(io.open('bower.json').read())
    for package_name, bower_version in bower_contents['dependencies'].items():
        # Normalize underscores to dashes
        package_name = package_name.replace('_', '-')
        if package_name in installed_things:
            python_version = installed_things[package_name].version
            if python_version != bower_version:
                raise AssertionError(
                    'Versions in python do not agree with bower versions:\n'
                    'Package: {}\n'
                    'Bower: {}\n'
                    'Python: {}'.format(
                        package_name, bower_version, python_version,
                    )
                )


def main():  # pragma: no cover
    print('Checking requirements...')
    # Forces quiet output and overrides pytest.ini
    os.environ['PYTEST_ADDOPTS'] = '-q -s'
    return pytest.main([__file__.replace('pyc', 'py')] + sys.argv[1:])


if __name__ == '__main__':
    exit(main())
