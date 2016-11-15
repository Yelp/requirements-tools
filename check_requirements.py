from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import io
import itertools
import json
import os.path
import subprocess
import sys
from collections import defaultdict
from operator import attrgetter

import pkg_resources
import pytest


installed_things = {
    pkg.key: pkg
    for pkg in pkg_resources.working_set  # pylint:disable=not-an-iterable
}
REQUIREMENTS_FILES = frozenset(('requirements.txt', 'requirements-dev.txt'))


def parse_requirement(req):
    dumb_parse = pkg_resources.Requirement.parse(req)
    if dumb_parse.extras:
        extras = '[{}]'.format(','.join(dumb_parse.extras))
    else:
        extras = ''
    return pkg_resources.Requirement.parse(
        dumb_parse.project_name + extras + ','.join(
            operator + pkg_resources.safe_version(version)
            for operator, version in dumb_parse.specs
        )
    )


def get_lines_from_file(filename):
    with io.open(filename) as requirements_file:
        return [
            line.strip() for line in requirements_file
            if line.strip() and not line.startswith('#')
        ]


def get_raw_requirements(filename):
    lines = get_lines_from_file(filename)
    return [
        (parse_requirement(line), filename)
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


@pytest.fixture(autouse=True, scope='session')
def check_requirements_is_only_for_applications():
    if not os.path.exists('requirements.txt'):
        raise AssertionError(
            'check-requirements is designed specifically with applications '
            'in mind (and does not properly work for libraries).\n'
            "Either remove check-requirements (if you're a library) or "
            '`touch requirements.txt`.'
        )


def _get_all_raw_requirements(requirements_files=REQUIREMENTS_FILES):
    # for compatibility with repos that haven't started using
    # requirements-dev-minimal.txt, we don't want to force pinning
    # requirements-dev.txt until they use minimal
    if not os.path.exists('requirements-dev-minimal.txt'):
        requirements_files -= {'requirements-dev.txt'}

    if all(
            not os.path.exists(reqfile)
            for reqfile in requirements_files
    ):  # pragma: no cover
        return

    return list(itertools.chain.from_iterable([
        get_raw_requirements(reqfile)
        for reqfile in requirements_files
        if os.path.exists(reqfile)
    ]))


@pytest.fixture(autouse=True, scope='session')
def check_requirements_integrity():
    raw_requirements = _get_all_raw_requirements()
    incorrect = []
    for req, filename in raw_requirements:
        version = to_version(req)
        if version is None:  # Not pinned, just skip
            continue
        installed_version = to_version(parse_requirement('{}=={}'.format(
            req.key, installed_things[req.key].version,
        )))
        if installed_version != version:
            incorrect.append((filename, req.key, version, installed_version))
    if incorrect:
        raise AssertionError(
            'Installed requirements do not match requirement files!\n'
            'Rebuild your virtualenv:\n{}'.format(''.join(
                ' - ({}) {}=={} (installed) {}=={}\n'.format(
                    filename, pkg, depped, pkg, installed,
                )
                for filename, pkg, depped, installed in incorrect
            ))
        )


def test_requirements_pinned():
    raw_requirements = _get_all_raw_requirements()
    if raw_requirements is None:  # pragma: no cover
        pytest.skip('No requirements files found')

    unpinned_requirements = find_unpinned_requirements(raw_requirements)
    if unpinned_requirements:
        raise AssertionError(
            'Unpinned requirements detected!\n\n{}'.format(
                format_unpinned_requirements(unpinned_requirements),
            )
        )


def get_pinned_versions_from_requirement(requirement):
    expected_pinned = set()
    requirements_to_parse = [requirement]

    # Need both key and extras (e.g., foo[bar]) to represent a
    # requirement; else we would skip foo[bar] after seeing foo.
    already_parsed = {(requirement.key, requirement.extras)}
    while requirements_to_parse:
        req = requirements_to_parse.pop()
        installed_req = installed_things[req.key]
        for sub_requirement in installed_req.requires(req.extras):
            sub_requirement_entry = (
                sub_requirement.key,
                sub_requirement.extras,
            )
            if sub_requirement_entry not in already_parsed:
                requirements_to_parse.append(sub_requirement)
                already_parsed.add(sub_requirement_entry)
            try:
                installed = installed_things[sub_requirement.key]
            except KeyError:
                raise AssertionError(
                    'Unmet dependency detected!\n'
                    'Somehow `{}` is not installed!\n'
                    '  (from {})\n'
                    'Are you suffering from '
                    'https://github.com/pypa/pip/issues/3903?'.format(
                        sub_requirement.key,
                        '{}[{}]'.format(req.key, ','.join(req.extras))
                        if req.extras else req.key,
                    ),
                )
            expected_pinned.add(
                '{}=={}'.format(installed.key, installed.version)
            )
    return expected_pinned


def format_versions_on_lines_with_dashes(versions):
    return '\n'.join(
        '\t- {}'.format(req)
        for req in sorted(versions, key=attrgetter('key'))
    )


def _expected_pinned(filename):
    ret = set()
    for req, _ in get_raw_requirements(filename):
        ret.add('{}=={}'.format(req.key, installed_things[req.key].version))
        ret |= get_pinned_versions_from_requirement(req)
    return ret


def test_top_level_dependencies():
    """Test that top-level requirements (reqs-minimal and reqs-dev-minimal)
    are consistent with the pinned requirements.
    """
    if all(
            not os.path.exists(path) for path in (
                'requirements-minimal.txt',
                'requirements.txt',
                'requirements-dev-minimal.txt',
                'requirements-dev.txt',
            )
    ):  # pragma: no cover
        pytest.skip('No requirements files')

    expected_pinned_prod = _expected_pinned('requirements-minimal.txt')
    environments = [
        (
            expected_pinned_prod,
            'requirements.txt',
            'requirements-minimal.txt',
        ),
    ]

    if os.path.exists('requirements-dev-minimal.txt'):
        expected_pinned_dev = _expected_pinned('requirements-dev-minimal.txt')
        # if there are overlapping prod/dev deps, only list in prod
        # requirements
        expected_pinned_dev -= expected_pinned_prod
        environments.append((
            expected_pinned_dev,
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
        expected_pinned = {parse_requirement(s) for s in expected_pinned}
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
                'Requirements are pinned in {pin} but are not depended on in {minimal}!\n'  # noqa
                '\n'
                'Usually this happens because you upgraded some other dependency, and now no longer require these.\n'  # noqa
                "If that's the case, you should remove these from {pin}.\n"  # noqa
                'Otherwise, if you *do* need these packages, then add them to {minimal}.\n'  # noqa
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


def test_javascript_package_versions():
    """Make sure package.json versions agree with python versions."""
    if not os.path.exists('package.json'):  # pragma: no cover
        pytest.skip('No JavaScript dependencies (package.json)')

    js_packages = defaultdict(set)

    with io.open('package.json') as f:
        contents = json.load(f)
    for package_name, version in contents.get('dependencies', {}).items():
        # Normalize underscores to dashes
        package_name = package_name.replace('_', '-')
        js_packages[package_name].add(version)

    for package_name, versions in js_packages.items():
        # Check against Python version
        version, = versions
        if package_name in installed_things:
            python_version = installed_things[package_name].version
            if python_version != version:
                raise AssertionError(
                    'The package "{}" is both a JavaScript and Python package.\n'  # noqa
                    "The version installed by Python must match the JavaScript version, but it currently doesn't!\n"  # noqa
                    '  JavaScript version: {}\n'
                    '  Python version: {}\n'
                    'Check requirements.txt and package.json!'.format(
                        package_name, version, python_version,
                    )
                )


def parse_npm_dependency_tree(tree):
    """Parse output of npm list --json.

    Return format is a dictionary with one key per package. Each value is
    another dictionary of installed versions for that package. The values of
    the inner dictionary are the set of packages that depended on them.

    For example:
    {
        'package': {
            '1.3': {'yelp-derp@1.2.3', 'express@9.4'},
            '4.5.9': {'something@4'},
        },
    }
    """
    ret = defaultdict(lambda: defaultdict(set))

    def inner(cur, name=None, parent=None):
        if name:
            # We exclude jquery's tree because it pulls in 75 dependencies
            # which we don't want to pin ourselves. Besides, we don't actually
            # use jQuery in prod (we load it from a CDN).
            if name == 'jquery':
                return
            if tree is parent:
                parent_dep = '(your app)@*'
            else:
                parent_dep = '{}@{}'.format(
                    parent['name'], parent.get('version', '*'),
                )
            ret[name][cur['version']].add(parent_dep)
            cur['name'] = name
        for dep_name, dep in cur.get('dependencies', {}).items():
            inner(dep, name=dep_name, parent=cur)
    inner(tree)
    return ret


def npm_installed_reason(npm_list, package, version):
    """Return string for why a package is installed."""
    if package not in npm_list:
        return ''

    wanted_by = npm_list[package][version]
    first_wanter = sorted(wanted_by)[0]
    return '<-{}{}'.format(
        first_wanter,
        npm_installed_reason(npm_list, *first_wanter.split('@')),
    )


def bold(text):  # pragma: no cover
    if sys.stderr.isatty():
        return '\033[1m{}\033[0m'.format(text)
    else:
        return text


def test_all_npm_packages_pinned():
    if not os.path.exists('package.json'):  # pragma: no cover
        pytest.skip('No package.json file')

    if not os.path.exists('node_modules'):
        raise AssertionError(
            'node_modules not found.  Are you missing a make target?',
        )

    npm_list = parse_npm_dependency_tree(json.loads(subprocess.check_output(
        ('npm', 'list', '--json', '--prod'),
        stderr=open(os.devnull, 'w'),
    ).decode('UTF-8')))

    package_json = json.load(io.open('package.json'))
    unpinned = set()
    for name, versions in npm_list.items():
        version = sorted(versions.keys())[0]
        if package_json['dependencies'].get(name) != version:
            unpinned.add('{} {}'.format(
                bold('{}@{}'.format(name, version)),
                npm_installed_reason(npm_list, name, version),
            ))

    if unpinned:
        raise AssertionError('Unpinned requirements detected!\n    {}'.format(
            '\n    '.join(sorted(unpinned)),
        ))


def test_no_conflicting_npm_package_versions():
    """Check for unsatisfiable version conflicts.

    If two packages depend on different versions of the same library, npm will
    install two nested copies. This doesn't work for frontend web packages, so
    we check for it.
    """
    if not os.path.exists('package.json'):  # pragma: no cover
        pytest.skip('No package.json file')

    if not os.path.exists('node_modules'):
        raise AssertionError(
            'node_modules not found.  Are you missing a make target?',
        )

    npm_list = parse_npm_dependency_tree(json.loads(subprocess.check_output(
        ('npm', 'list', '--json', '--prod'),
        stderr=open(os.devnull, 'w'),
    ).decode('UTF-8')))

    duplicates = set()
    for name, versions in npm_list.items():
        if len(versions) > 1:
            duplicates.add(
                '{} needs multiple versions:\n    {}'.format(
                    bold(name),
                    '\n    '.join(
                        '{} {}'.format(
                            bold('{}@{}'.format(name, version)),
                            npm_installed_reason(
                                npm_list,
                                name,
                                version,
                            ),
                        )
                        for version, why in sorted(versions.items())
                    ),
                ),
            )

    if duplicates:
        raise AssertionError(
            'Conflicting NPM package requirements detected!\n  {}'.format(
                '\n  '.join(sorted(duplicates)),
            ),
        )


def main():  # pragma: no cover
    print('Checking requirements...')
    # Forces quiet output and overrides pytest.ini
    os.environ['PYTEST_ADDOPTS'] = '-q -s --tb=short'
    return pytest.main([__file__.replace('pyc', 'py')] + sys.argv[1:])


if __name__ == '__main__':
    exit(main())
