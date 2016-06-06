# pylint:disable=redefined-outer-name
from __future__ import absolute_import
from __future__ import unicode_literals

import contextlib
import io
import json
import os
import re
import subprocess

import mock
import pkg_resources
import pytest

import check_requirements as main


def write_file(filename, contents):
    with io.open(filename, 'w') as f:
        f.write(contents)


@pytest.mark.parametrize(
    ('reqin', 'reqout'),
    (
        ('a', 'a'),
        ('a==1', 'a==1'),
        ('a==1,<3', 'a==1,<3'),
    ),
)
def test_parse_requirement(reqin, reqout):
    assert (
        main.parse_requirement(reqin) ==
        pkg_resources.Requirement.parse(reqout)
    )


def test_get_lines_from_file_trivial(tmpdir):
    tmpfile = tmpdir.join('foo').strpath
    write_file(tmpfile, '')
    assert main.get_lines_from_file(tmpfile) == []


def test_get_lines_from_file_ignores_comments(tmpdir):
    tmpfile = tmpdir.join('foo').strpath
    write_file(tmpfile, 'foo\n#bar\nbaz')
    assert main.get_lines_from_file(tmpfile) == ['foo', 'baz']


def test_get_lines_from_file_strips_ws(tmpdir):
    tmpfile = tmpdir.join('foo').strpath
    write_file(tmpfile, ' foo \n    \n \tbaz')
    assert main.get_lines_from_file(tmpfile) == ['foo', 'baz']


def test_get_raw_requirements_trivial(tmpdir):
    reqs_filename = tmpdir.join('requirements.txt').strpath
    write_file(reqs_filename, '')
    assert main.get_raw_requirements(reqs_filename) == []


def test_get_raw_requirements_some_things(tmpdir):
    reqs_filename = tmpdir.join('requirements.txt').strpath
    write_file(reqs_filename, '-e .\nfoo==1\nbar==2')
    requirements = main.get_raw_requirements(reqs_filename)
    assert requirements == [
        (pkg_resources.Requirement.parse('foo==1'), reqs_filename),
        (pkg_resources.Requirement.parse('bar==2'), reqs_filename),
    ]


def test_to_version():
    assert main.to_version(pkg_resources.Requirement.parse('foo==2')) == '2'
    assert main.to_version(pkg_resources.Requirement.parse('foo')) is None
    assert main.to_version(pkg_resources.Requirement.parse('foo>3')) is None
    assert main.to_version(pkg_resources.Requirement.parse('foo>3,<7')) is None


def test_to_equality_str():
    req = pkg_resources.Requirement.parse('foo==2.2')
    assert main.to_equality_str(req) == 'foo==2.2'


def test_to_pinned_versions_trivial():
    assert main.to_pinned_versions(()) == {}


def test_to_pinned_versions():
    pinned_versions = main.to_pinned_versions((
        (pkg_resources.Requirement.parse('foo==2'), 'reqs.txt'),
        (pkg_resources.Requirement.parse('bar==3'), 'reqs.txt'),
    ))
    assert pinned_versions == {'foo': '2', 'bar': '3'}


def test_to_pinned_versions_uses_key():
    pinned_versions = main.to_pinned_versions((
        (pkg_resources.Requirement.parse('Foo==2'), 'reqs.txt'),
    ))
    assert pinned_versions == {'foo': '2'}


def test_unpinned_things():
    flake8req = pkg_resources.Requirement.parse('flake8==2.3.0')
    ret = main.find_unpinned_requirements(((flake8req, 'reqs.txt'),))
    assert ret == {
        ('mccabe', flake8req, 'reqs.txt'),
        ('pep8', flake8req, 'reqs.txt'),
        ('pyflakes', flake8req, 'reqs.txt'),
    }


def test_format_unpinned_requirements():
    unpinned = main.find_unpinned_requirements((
        (pkg_resources.Requirement.parse('flake8==2.3.0'), 'reqs.txt'),
    ))
    ret = main.format_unpinned_requirements(unpinned)
    assert ret == (
        "\tmccabe (required by flake8==2.3.0 in reqs.txt)\n"
        '\t\tmaybe you want "mccabe==0.4.0"?\n'
        "\tpep8 (required by flake8==2.3.0 in reqs.txt)\n"
        '\t\tmaybe you want "pep8==1.7.0"?\n'
        "\tpyflakes (required by flake8==2.3.0 in reqs.txt)\n"
        '\t\tmaybe you want "pyflakes==1.0.0"?'
    )


@pytest.yield_fixture
def mock_package_name():
    with mock.patch.object(main, 'get_package_name', return_value='pkg'):
        yield


@pytest.yield_fixture
def mock_pinned_from_requirement_ab():
    with mock.patch.object(
        main,
        'get_pinned_versions_from_requirement',
        return_value={'a==1', 'b==2'},
    ):
        yield


@pytest.yield_fixture
def mock_pinned_from_requirement_abc():
    with mock.patch.object(
        main,
        'get_pinned_versions_from_requirement',
        return_value={'a==1', 'b==2', 'c==3'},
    ):
        yield


@pytest.yield_fixture
def mock_get_raw_requirements_ab():
    with mock.patch.object(
        main,
        'get_raw_requirements',
        return_value={
            (pkg_resources.Requirement.parse('a==1'), 'r.txt'),
            (pkg_resources.Requirement.parse('b==2'), 'r.txt'),
        },
    ):
        yield


@pytest.yield_fixture
def mock_get_raw_requirements_abc():
    with mock.patch.object(
        main,
        'get_raw_requirements',
        return_value={
            (pkg_resources.Requirement.parse('a==1'), 'r.txt'),
            (pkg_resources.Requirement.parse('b==2'), 'r.txt'),
            (pkg_resources.Requirement.parse('c==3'), 'r.txt'),
        },
    ):
        yield


@pytest.mark.usefixtures(
    'in_tmpdir', 'mock_package_name',
    'mock_pinned_from_requirement_abc', 'mock_get_raw_requirements_abc',
)
def test_test_top_level_dependencies():
    # So we don't skip
    write_file('setup.py', '')
    write_file('requirements.txt', '')
    # Should pass since all are satisfied
    main.test_top_level_dependencies()


@pytest.mark.usefixtures(
    'in_tmpdir', 'mock_package_name',
    'mock_pinned_from_requirement_abc', 'mock_get_raw_requirements_ab',
)
def test_test_top_level_dependencies_too_much_pinned():
    # So we don't skip
    write_file('setup.py', '')
    write_file('requirements.txt', '')
    with pytest.raises(AssertionError) as excinfo:
        main.test_top_level_dependencies()
    assert excinfo.value.args == (
        'Dependencies derived from setup.py are not pinned in '
        'requirements.txt\n'
        '(Probably need to add something to requirements.txt):\n'
        '\t- c==3',
    )


@pytest.mark.usefixtures('in_tmpdir')
@pytest.mark.parametrize('version', ('1.2.3-rc1', '1.2.3rc1'))
def test_prerelease_name_normalization(version):
    write_file(
        'setup.py',
        'from setuptools import setup\n'
        'setup(\n'
        '    name="depends-on-prerelease-pkg",\n'
        '    install_requires=["prerelease-pkg"],\n'
        ')\n'
    )
    write_file('requirements.txt', 'prerelease-pkg=={}'.format(version))
    main.test_top_level_dependencies()


@contextlib.contextmanager
def mocked_package(package_name='pkg', prod_deps=(), dev_deps=()):
    def fake_get_pinned_versions_from_requirement(req):
        """If it's the package itself, return prod deps. If it's any other
        package, assume it's a dev dep and return all dev dependencies.

        This is not great but short of real integration tests it works...
        """
        if req == package_name:
            deps = prod_deps
        else:
            deps = dev_deps
        return set(['=='.join(dep) for dep in deps])

    with mock.patch.object(
        main,
        'get_pinned_versions_from_requirement',
        side_effect=fake_get_pinned_versions_from_requirement,
    ), mock.patch.object(
        main,
        'installed_things',
        {
            package: mock.Mock(version=version)
            for package, version in prod_deps + dev_deps
        }
    ):
        yield


@pytest.mark.usefixtures('in_tmpdir', 'mock_package_name')
def test_test_top_level_dependencies_no_requirements_dev_minimal():
    """If there's no requirements-dev-minimal.txt, we should suggest you create
    a requirements-dev-minimal.txt but not fail."""
    write_file('requirements-dev.txt', 'a\nb==3\n')
    with mocked_package(dev_deps=(('a', '4'), ('b', '3'))):
        with mock.patch.object(main, 'print') as fake_print:
            main.test_top_level_dependencies()  # should not raise
    assert (
        'Warning: check-requirements is *not* checking your dev dependencies.'
        in fake_print.call_args[0][0]
    )


@pytest.mark.usefixtures('in_tmpdir', 'mock_package_name')
def test_test_top_level_dependencies_no_dev_deps_pinned():
    """If there's a requirements-dev-minimal.txt but no requirements-dev.txt,
    we should tell you to pin everything there."""
    write_file('requirements-dev-minimal.txt', 'a\nb\n')
    with mocked_package(dev_deps=(('a', '2'), ('b', '3'))):
        with pytest.raises(AssertionError) as excinfo:
            main.test_top_level_dependencies()
        assert excinfo.value.args == (
            'Dependencies derived from requirements-dev-minimal.txt are '
            'not pinned in requirements-dev.txt\n'
            '(Probably need to add something to requirements-dev.txt):\n'
            '\t- a==2\n'
            '\t- b==3',
        )

        # and when you do pin it, now the tests pass! :D
        write_file('requirements-dev.txt', 'a==2\nb==3\n')
        main.test_top_level_dependencies()


@pytest.mark.usefixtures('in_tmpdir', 'mock_package_name')
def test_test_top_level_dependencies_some_dev_deps_not_pinned():
    """If there's a requirements-dev-minimal.txt but we're missing stuff in
    requirements-dev.txt, we should tell you to pin more stuff there."""
    write_file('requirements-dev-minimal.txt', 'a\nb\n')
    write_file('requirements-dev.txt', 'a==2\n')
    with mocked_package(dev_deps=(('a', '2'), ('b', '3'))):
        with pytest.raises(AssertionError) as excinfo:
            main.test_top_level_dependencies()
        assert excinfo.value.args == (
            'Dependencies derived from requirements-dev-minimal.txt are '
            'not pinned in requirements-dev.txt\n'
            '(Probably need to add something to requirements-dev.txt):\n'
            '\t- b==3',
        )

        # and when you do pin it, now the tests pass! :D
        write_file('requirements-dev.txt', 'a==2\nb==3\n')
        main.test_top_level_dependencies()


@pytest.mark.usefixtures('in_tmpdir', 'mock_package_name')
def test_test_top_level_dependencies_overlapping_prod_dev_deps():
    """If we have a dep which is both a prod and dev dep, we should complain if
    it appears in requirements-dev.txt."""
    write_file('requirements-dev-minimal.txt', 'a\n')
    write_file('requirements.txt', 'a==2\n')
    write_file('requirements-dev.txt', 'a==2\n')
    with mocked_package(prod_deps=[('a', '2')], dev_deps=[('a', '2')]):
        with pytest.raises(AssertionError) as excinfo:
            main.test_top_level_dependencies()
        # TODO: this exception is misleading, ideally it should tell you that
        # you don't need to pin it in reqs-dev.txt if it's also a prod dep
        assert excinfo.value.args == (
            'Requirements are pinned in requirements-dev.txt '
            'but are not depended on in requirements-dev-minimal.txt\n'
            '(Probably need to add something to '
            'requirements-dev-minimal.txt)\n'
            '(or remove from requirements-dev.txt):\n'
            '\t- a==2',
        )


@pytest.mark.usefixtures('in_tmpdir', 'mock_package_name')
def test_test_top_level_dependencies_prod_dep_is_only_in_dev_deps():
    """If we've defined a prod dependency only in requirements-dev.txt, we
    should tell the user to put it in requirements.txt instead."""
    write_file('requirements-dev-minimal.txt', 'a\n')
    write_file('requirements.txt', '')
    write_file('requirements-dev.txt', 'a==2\n')
    with mocked_package(prod_deps=[('a', '2')], dev_deps=[('a', '2')]):
        with pytest.raises(AssertionError) as excinfo:
            main.test_top_level_dependencies()
        assert excinfo.value.args == (
            'Dependencies derived from setup.py are not pinned in '
            'requirements.txt\n'
            '(Probably need to add something to requirements.txt):\n'
            '\t- a==2',
        )


@pytest.mark.usefixtures(
    'in_tmpdir', 'mock_package_name',
    'mock_pinned_from_requirement_ab', 'mock_get_raw_requirements_abc',
)
def test_test_top_level_dependencies_not_enough_pinned():
    # So we don't skip
    write_file('setup.py', '')
    write_file('requirements.txt', '')
    with pytest.raises(AssertionError) as excinfo:
        main.test_top_level_dependencies()
    assert excinfo.value.args == (
        'Requirements are pinned in requirements.txt but are not depended '
        'on in setup.py\n'
        '(Probably need to add something to setup.py)\n'
        '(or remove from requirements.txt):\n'
        '\t- c==3',
    )


@pytest.mark.usefixtures('in_tmpdir')
def test_test_requirements_pinned_trivial():
    write_file('requirements.txt', '')
    # Should not raise
    main.test_requirements_pinned()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_requirements_pinned_trivial_with_dev_too():
    write_file('requirements.txt', '')
    write_file('requirements-dev.txt', '')
    # Should not raise
    main.test_requirements_pinned()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_requirements_pinned_all_pinned():
    write_file(
        'requirements.txt',
        'flake8==2.3.0\n'
        'pep8==1.6.1\n'
        'mccabe==0.3\n'
        'pyflakes==0.8.1\n'
    )
    # Should also not raise (all satisfied)
    main.test_requirements_pinned()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_requirements_pinned_all_pinned_dev_only():
    write_file('requirements-dev-minimal.txt', 'flake8==2.3.0')
    write_file(
        'requirements-dev.txt',
        'flake8==2.3.0\n'
        'pep8==1.6.1\n'
        'mccabe==0.3\n'
        'pyflakes==0.8.1\n'
    )
    # Should also not raise (all satisfied)
    main.test_requirements_pinned()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_requirements_pinned_missing_some():
    write_file(
        'requirements.txt',
        'flake8==2.3.0',
    )
    write_file(
        'requirements-dev.txt',
        'astroid==1.4.3',
    )
    with pytest.raises(AssertionError) as excinfo:
        main.test_requirements_pinned()
    assert excinfo.value.args == (
        'Unpinned requirements detected!\n\n'
        '\tmccabe (required by flake8==2.3.0 in requirements.txt)\n'
        '\t\tmaybe you want "mccabe==0.4.0"?\n'
        '\tpep8 (required by flake8==2.3.0 in requirements.txt)\n'
        '\t\tmaybe you want "pep8==1.7.0"?\n'
        '\tpyflakes (required by flake8==2.3.0 in requirements.txt)\n'
        '\t\tmaybe you want "pyflakes==1.0.0"?',
    )


@pytest.mark.usefixtures('in_tmpdir')
def test_test_requirements_pinned_missing_some_with_dev_reqs():
    write_file(
        'requirements.txt',
        'flake8==2.3.0',
    )
    write_file(
        'requirements-dev.txt',
        'astroid==1.4.5',
    )
    write_file(
        'requirements-dev-minimal.txt',
        'astroid',
    )
    with pytest.raises(AssertionError) as excinfo:
        main.test_requirements_pinned()
    assert excinfo.value.args == (
        'Unpinned requirements detected!\n\n'
        '\tlazy-object-proxy (required by astroid==1.4.5 in requirements-dev.txt)\n'  # noqa
        '\t\tmaybe you want "lazy-object-proxy==1.2.2"?\n'
        '\tmccabe (required by flake8==2.3.0 in requirements.txt)\n'
        '\t\tmaybe you want "mccabe==0.4.0"?\n'
        '\tpep8 (required by flake8==2.3.0 in requirements.txt)\n'
        '\t\tmaybe you want "pep8==1.7.0"?\n'
        '\tpyflakes (required by flake8==2.3.0 in requirements.txt)\n'
        '\t\tmaybe you want "pyflakes==1.0.0"?\n'
        '\tsix (required by astroid==1.4.5 in requirements-dev.txt)\n'
        '\t\tmaybe you want "six==1.10.0"?\n'
        '\twrapt (required by astroid==1.4.5 in requirements-dev.txt)\n'
        '\t\tmaybe you want "wrapt==1.10.8"?',
    )


@pytest.yield_fixture
def in_tmpdir(tmpdir):
    pwd = os.getcwd()
    os.chdir(tmpdir.strpath)
    try:
        yield tmpdir
    finally:
        os.chdir(pwd)


@pytest.mark.usefixtures('in_tmpdir')
def test_get_package_name():
    write_file('setup.py', 'from setuptools import setup\nsetup(name="foo")')
    assert main.get_package_name() == 'foo'


def test_get_pinned_versions_from_requirement():
    result = main.get_pinned_versions_from_requirement('flake8')
    # These are to make this not flaky in future when things change
    assert isinstance(result, set)
    result = sorted(result)
    split = [req.split('==') for req in result]
    packages = [package for package, _ in split]
    assert packages == ['mccabe', 'pep8', 'pyflakes']


def test_get_pinned_versions_from_requirement_circular():
    # Used to hang forever
    assert main.get_pinned_versions_from_requirement('sphinx')


def test_format_versions_on_lines_with_dashes_trivial():
    assert main.format_versions_on_lines_with_dashes(()) == ''


def test_format_versions_on_lines_with_dashes_something():
    versions = [
        pkg_resources.Requirement.parse('a==4.5.6'),
        pkg_resources.Requirement.parse('b==1.2.3'),
        pkg_resources.Requirement.parse('c==7'),
    ]
    ret = main.format_versions_on_lines_with_dashes(versions)
    assert ret == (
        '\t- a==4.5.6\n'
        '\t- b==1.2.3\n'
        '\t- c==7'
    )


@pytest.mark.usefixtures('in_tmpdir')
def test_test_no_underscores_passes_reqs_dev_doesnt_exist():
    """If requirements.txt exists (but not -dev.txt) we shouldn't raise."""
    write_file('requirements.txt', 'foo==1')
    # Should not raise
    main.test_no_underscores_all_dashes()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_no_underscores_all_dashes_ok():
    tmpfile = 'tmp'
    write_file(tmpfile, 'foo==1')
    # Should not raise
    main.test_no_underscores_all_dashes(requirements_files=(tmpfile,))


@pytest.mark.usefixtures('in_tmpdir')
def test_test_no_underscores_all_dashes_error():
    tmpfile = 'tmp'
    write_file(tmpfile, 'foo_bar==1')
    with pytest.raises(AssertionError) as excinfo:
        main.test_no_underscores_all_dashes(requirements_files=(tmpfile,))
    assert excinfo.value.args == (
        'Use dashes for package names tmp: foo_bar==1',
    )


@pytest.mark.usefixtures('in_tmpdir')
def test_test_javascript_package_versions_no_bower_versions():
    write_file('bower.json', '{"dependencies": {}}')
    # Should not raise
    main.test_javascript_package_versions()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_javascript_package_versions_matching():
    # TODO: use a dummy package to prevent flake8 upgrade + test breaking
    # Contrived, but let's assume flake8 is a bower package
    write_file('bower.json', '{"dependencies": {"flake8": "2.5.4"}}')
    # Should not raise
    main.test_javascript_package_versions()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_bower_package_irrelevant_version():
    # I hope we don't install a python package named jquery any time soon :)
    write_file('bower.json', '{"dependencies": {"jquery": "1.10.0"}}')
    # Should not raise
    main.test_javascript_package_versions()


@pytest.mark.usefixtures('in_tmpdir')
@pytest.mark.parametrize('js_file', ['bower.json', 'package.json'])
def test_test_javascript_package_versions_not_matching_python(js_file):
    # TODO: use a dummy package to prevent flake8 upgrade + test breaking
    # Again, contrived, but let's assume flake8 is a bower and/or npm package
    write_file(js_file, '{"dependencies": {"flake8": "0.0.0"}}')
    with pytest.raises(AssertionError) as excinfo:
        main.test_javascript_package_versions()
    assert excinfo.value.args == (
        'Versions in python do not agree with JavaScript versions:\n'
        '  Package: flake8\n'
        '  JavaScript: 0.0.0\n'
        '  Python: 2.5.4',
    )


@pytest.mark.usefixtures('in_tmpdir')
def test_test_javascript_package_versions_conflicting_bower_and_npm_versions():
    write_file('bower.json', '{"dependencies": {"left-pad": "0.0.1"}}')
    write_file('package.json', '{"dependencies": {"left-pad": "0.0.2"}}')
    with pytest.raises(AssertionError) as excinfo:
        main.test_javascript_package_versions()
    assert excinfo.value.args == (
        'Multiple different versions of a package are installed by '
        'different JavaScript package managers:\n'
        '  Package: left-pad\n'
        '  Installed versions: 0.0.1, 0.0.2\n'
        'Make sure bower.json and package.json agree!',
    )


@pytest.mark.usefixtures('in_tmpdir')
def test_test_javascript_package_versions_agreeable_bower_and_npm_versions():
    write_file('bower.json', '{"dependencies": {"left-pad": "0.0.2"}}')
    write_file('package.json', '{"dependencies": {"left-pad": "0.0.2"}}')
    main.test_javascript_package_versions()


@pytest.mark.usefixtures('in_tmpdir')
def test_check_requirements_is_only_for_applications():
    write_file('requirements.txt', '')
    main.check_requirements_is_only_for_applications()


def test_check_requirements_is_only_for_applications_failing():
    with pytest.raises(AssertionError) as excinfo:
        main.check_requirements_is_only_for_applications()
    assert excinfo.value.args == (
        'check-requirements is designed specifically with applications in '
        'mind (and does not properly work for libraries).\n'
        "Either remove check-requirements (if you're a library) or "
        '`touch requirements.txt`.',
    )


@pytest.mark.parametrize(
    'version',
    (
        '<1',
        '<=1',
        '>1',
        '>=1',
        '1 || 2',
        '1 - 2',
        '1.2.x',
        '1.2.*',
        '*',
        '',
        '~1',
        '^1',
    ),
)
def test_bower_assert_pinned_bad(version):
    with pytest.raises(AssertionError):
        main.bower_assert_pinned('pkg', version)


def test_bower_assert_pined_ok():
    main.bower_assert_pinned('pkg', '1.2.3')


def resource(f):
    return os.path.join(os.path.dirname(__file__), 'testing', f)


@pytest.fixture
def passing_bower_list():
    with io.open(resource('passing_bower_list.json')) as f:
        return json.load(f)


@pytest.fixture
def failing_bower_list():
    with io.open(resource('failing_bower_list.json')) as f:
        return json.load(f)


def test_bower_find_unpinned_all_pinned(passing_bower_list):
    assert main.bower_find_unpinned(passing_bower_list) == set()


def test_bower_find_unpinned_with_unpinned(failing_bower_list):
    assert main.bower_find_unpinned(failing_bower_list) == {
        ('jquery', '2.2.1', '"flot": "0.8.3"'),
    }


def test_bower_format_unpinned_requirements():
    ret = main.bower_format_unpinned_requirements({
        ('f', '2', '"c": "1"'),
        ('a', '1', '"b": "1"'),
    })
    assert ret == (
        '\ta (required by "b": "1" in bower.json)\n'
        '\t\tmaybe you want "a": "1"?\n'
        '\tf (required by "c": "1" in bower.json)\n'
        '\t\tmaybe you want "f": "2"?'
    )


@contextlib.contextmanager
def subprocess_returns(this):
    with mock.patch.object(
        subprocess, 'check_output',
        return_value=json.dumps(this).encode('UTF-8'),
    ):
        yield


def uncolor(text):
    text = re.sub('\033\\[[^A-z]*[A-z]', '', text)
    return re.sub('[^\n\r]*\r', '', text)


@pytest.mark.usefixtures('in_tmpdir')
def test_all_bower_packages_pinned_passing(passing_bower_list):
    write_file('bower.json', '{}')
    with subprocess_returns(passing_bower_list):
        main.test_all_bower_packages_pinned()


@pytest.mark.usefixtures('in_tmpdir')
def test_all_bower_packages_pinned_failing(failing_bower_list):
    write_file('bower.json', '{}')
    with pytest.raises(AssertionError) as excinfo:
        with subprocess_returns(failing_bower_list):
            main.test_all_bower_packages_pinned()
    assert excinfo.value.args == (
        'Unpinned requirements detected!\n\n'
        '\tjquery (required by "flot": "0.8.3" in bower.json)\n'
        '\t\tmaybe you want "jquery": "2.2.1"?',
    )


@pytest.mark.parametrize('tree,expected', [
    (
        {'name': 'www_pages', 'dependencies': {}},
        {},
    ),
    (
        {
            'name': 'www_pages',
            'dependencies': {'closure_compiler': {'version': '1.0'}},
        },
        {
            'closure_compiler': {'1.0': {'www_pages@*'}},
        },
    ),
    (
        {
            'name': 'www_pages',
            'dependencies': {
                'closure_compiler': {
                    'version': '1.0',
                    'dependencies': {'closure_externs': {'version': '2.0'}}
                },
            },
        },
        {
            'closure_compiler': {'1.0': {'www_pages@*'}},
            'closure_externs': {'2.0': {'closure_compiler@1.0'}},
        },
    ),
    (
        {
            'name': 'www_pages',
            'dependencies': {
                'closure_compiler': {
                    'version': '1.0',
                    'dependencies': {'closure_externs': {'version': '2.0'}}
                },
                'closure_externs': {'version': '2.0'},
            },
        },
        {
            'closure_compiler': {'1.0': {'www_pages@*'}},
            'closure_externs': {
                '2.0': {'closure_compiler@1.0', 'www_pages@*'},
            },
        },
    ),
    (
        {
            'name': 'www_pages',
            'dependencies': {
                'closure_compiler': {
                    'version': '1.0',
                    'dependencies': {'closure_externs': {'version': '2.0'}}
                },
                'closure_externs': {'version': '3.0'},
            },
        },
        {
            'closure_compiler': {'1.0': {'www_pages@*'}},
            'closure_externs': {
                '2.0': {'closure_compiler@1.0'},
                '3.0': {'www_pages@*'},
            },
        },
    ),
    # jquery tree should be ignored entirely
    (
        {
            'name': 'www_pages',
            'dependencies': {
                'jquery': {
                    'version': '1.0',
                    'dependencies': {'closure_externs': {'version': '2.0'}}
                },
            },
        },
        {},
    ),
])
def test_parse_npm_dependency_tree(tree, expected):
    assert main.parse_npm_dependency_tree(tree) == expected


@pytest.mark.parametrize('tree,package_json', [
    (
        {'name': 'www_pages', 'dependencies': {}},
        {'dependencies': {}},
    ),
    (
        {
            'name': 'www_pages',
            'dependencies': {
                'closure_compiler': {
                    'version': '1.0',
                    'dependencies': {'closure_externs': {'version': '2.0'}},
                },
            },
        },
        {
            'dependencies': {
                'closure_compiler': '1.0',
                'closure_externs': '2.0',
            }
        },
    ),
    (
        {
            'name': 'www_pages',
            'dependencies': {
                'closure_compiler': {
                    'version': '1.0',
                    'dependencies': {'closure_externs': {'version': '2.0'}},
                },
                'closure_externs': {'version': '2.0'},
            },
        },
        {
            'dependencies': {
                'closure_compiler': '1.0',
                'closure_externs': '2.0',
            }
        },
    ),
])
def test_test_all_npm_packages_pinned_success(tree, package_json, tmpdir):
    with subprocess_returns(tree), tmpdir.as_cwd():
        with tmpdir.join('package.json').open('w') as f:
            json.dump(package_json, f)
        main.test_all_npm_packages_pinned()


@pytest.mark.parametrize('tree,package_json,error', [
    (
        {
            'name': 'www_pages',
            'dependencies': {'closure_compiler': {'version': '1.0'}},
        },
        {'dependencies': {}},
        (
            'Unpinned requirements detected!\n'
            '    closure_compiler@1.0 from www_pages@*<-(package.json)'
        ),
    ),
    (
        {
            'name': 'www_pages',
            'dependencies': {
                'closure_compiler': {
                    'version': '1.0',
                    'dependencies': {
                        'closure_externs': {
                            'version': '2.0',
                            'dependencies': {
                                'left-pad': {'version': '3.0'},
                            }
                        }
                    }
                },
            },
        },
        {'dependencies': {'closure_externs': '2.0'}},
        (
            'Unpinned requirements detected!\n'
            '    closure_compiler@1.0 from www_pages@*<-(package.json)\n'
            '    left-pad@3.0 from closure_externs@2.0<-closure_compiler@1.0<-www_pages@*<-(package.json)'  # noqa
        ),
    ),
])
def test_test_all_npm_packages_pinned_failure(
        tree,
        package_json,
        error,
        tmpdir,
):
    with subprocess_returns(tree), tmpdir.as_cwd():
        with tmpdir.join('package.json').open('w') as f:
            json.dump(package_json, f)
        with pytest.raises(AssertionError) as excinfo:
            main.test_all_npm_packages_pinned()
    assert uncolor(excinfo.value.args[0]) == error


@pytest.mark.parametrize('tree,package_json', [
    (
        {'name': 'www_pages', 'dependencies': {}},
        {'dependencies': {}},
    ),
    (
        {
            'name': 'www_pages',
            'dependencies': {
                'closure_compiler': {
                    'version': '1.0',
                    'dependencies': {'closure_externs': {'version': '2.0'}},
                },
                'closure_externs': {'version': '2.0'},
            },
        },
        {
            'dependencies': {}
        },
    ),
])
def test_test_no_conflicting_npm_package_versions_success(
        tree,
        package_json,
        tmpdir,
):
    with subprocess_returns(tree), tmpdir.as_cwd():
        with tmpdir.join('package.json').open('w') as f:
            json.dump(package_json, f)
        main.test_no_conflicting_npm_package_versions()


@pytest.mark.parametrize('tree,package_json,error', [
    (
        {
            'name': 'www_pages',
            'dependencies': {
                'closure_compiler': {
                    'version': '4.0',
                    'dependencies': {'closure_externs': {'version': '1.0'}},
                },
                'closure_externs': {
                    'version': '2.0',
                    'dependencies': {
                        'closure_compiler': {'version': '9.999'},
                    },
                }
            },
        },
        {'dependencies': {}},
        (
            'Conflicting NPM package requirements detected!\n'
            '  closure_compiler needs multiple versions:\n'
            '    4.0 from (package.json)\n'
            '    9.999 from www_pages@*<-(package.json)\n'
            '  closure_externs needs multiple versions:\n'
            '    1.0 from www_pages@*<-(package.json)\n'
            '    2.0 from (package.json)'
        ),
    ),
])
def test_test_no_conflicting_npm_package_versions_failure(
        tree,
        package_json,
        error,
        tmpdir,
):
    with subprocess_returns(tree), tmpdir.as_cwd():
        with tmpdir.join('package.json').open('w') as f:
            json.dump(package_json, f)
        with pytest.raises(AssertionError) as excinfo:
            main.test_no_conflicting_npm_package_versions()
    assert uncolor(excinfo.value.args[0]) == error
