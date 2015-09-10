from __future__ import absolute_import
from __future__ import unicode_literals

import io
import json
import os.path
import subprocess
import sys

import pkg_resources
import pytest


installed_things = {pkg.key: pkg for pkg in pkg_resources.working_set}


def get_lines_from_file(filename):
    with io.open(filename) as requirements_file:
        return [
            line.strip() for line in requirements_file
            if line.strip() and not line.startswith('#')
        ]


def get_raw_requirements(filename):
    lines = get_lines_from_file(filename)
    return [
        (pkg_resources.Requirement.parse(line), filename) for line in lines
    ]


def to_version(requirement):
    if len(requirement.specs) != 1:
        raise AssertionError('Expected one spec: {!r}'.format(requirement))
    if requirement.specs[0][0] != '==':
        raise AssertionError('Expected == spec: {!r}'.format(requirement))
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

    unpinned = set()
    for requirement, filename in requirements:
        package_info = installed_things[requirement.key]

        for sub_requirement in package_info.requires(requirement.extras):
            if sub_requirement.key not in pinned_versions:
                unpinned.add(
                    (sub_requirement.project_name, requirement, filename)
                )
    return unpinned


def format_unpinned_requirements(unpinned_requirements):
    return '\t' + '\n\t'.join(
        '{} (required by {} in {})'.format(*req)
        for req in sorted(unpinned_requirements)
    )


def test_requirements_pinned(requirements_files=('requirements.txt',)):
    if all(
            not os.path.exists(reqfile)
            for reqfile in requirements_files
    ):  # pragma: no cover
        pytest.skip('No requirements files found')

    raw_requirements = sum(
        [get_raw_requirements(reqfile) for reqfile in requirements_files],
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
    requirements_to_parse = [installed_things[parsed.key]]
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
    return '\n'.join('\t- {}'.format(req) for req in sorted(versions))


def test_setup_dependencies():
    if (
            not os.path.exists('setup.py') or
            not os.path.exists('requirements.txt')
    ):  # pragma: no cover
        pytest.skip('No setup.py or requirements.txt')

    package_name = get_package_name()
    expected_pinned = get_pinned_versions_from_requirement(package_name)
    expected_pinned = {
        pkg_resources.Requirement.parse(s) for s in expected_pinned
    }
    requirements = {
        req for req, _ in get_raw_requirements('requirements.txt')
    }
    pinned_but_not_required = requirements - expected_pinned
    required_but_not_pinned = expected_pinned - requirements
    if pinned_but_not_required:
        raise AssertionError(
            'Requirements are pinned in requirements.txt but are not depended '
            'on in setup.py\n'
            '(Probably need to add something to setup.py):\n'
            '{}'.format(format_versions_on_lines_with_dashes(
                pinned_but_not_required,
            ))
        )
    if required_but_not_pinned:
        raise AssertionError(
            'Dependencies derived from setup.py are not pinned in '
            'requirements.txt\n'
            '(Probably need to add something to requirements.txt):\n'
            '{}'.format(format_versions_on_lines_with_dashes(
                required_but_not_pinned,
            )),
        )


def test_no_underscores_all_dashes(requirements_files=('requirements.txt',)):
    if all(
            not os.path.exists(reqfile)
            for reqfile in requirements_files
    ):  # pragma: no cover
        pytest.skip('No requirements files found')

    for requirement_file in requirements_files:
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
    return pytest.main([__file__.replace('pyc', 'py')] + sys.argv[1:])


if __name__ == '__main__':
    exit(main())
