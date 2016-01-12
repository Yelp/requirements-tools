from __future__ import absolute_import
from __future__ import unicode_literals

import io
import os

import mock
import pkg_resources
import pytest

from check_requirements import main


def write_file(filename, contents):
    with io.open(filename, 'w') as f:
        f.write(contents)


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
        '\t\tmaybe you want "mccabe==0.3.1"?\n'
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
def test_test_setup_dependencies_all_satisfied():
    # So we don't skip
    write_file('setup.py', '')
    write_file('requirements.txt', '')
    # Should pass since all are satisfied
    main.test_setup_dependencies()


@pytest.mark.usefixtures(
    'in_tmpdir', 'mock_package_name',
    'mock_pinned_from_requirement_abc', 'mock_get_raw_requirements_ab',
)
def test_test_setup_dependencies_too_much_pinned():
    # So we don't skip
    write_file('setup.py', '')
    write_file('requirements.txt', '')
    with pytest.raises(AssertionError) as excinfo:
        main.test_setup_dependencies()
    assert excinfo.value.args == (
        'Dependencies derived from setup.py are not pinned in '
        'requirements.txt\n'
        '(Probably need to add something to requirements.txt):\n'
        '\t- c==3',
    )


@pytest.mark.usefixtures(
    'in_tmpdir', 'mock_package_name',
    'mock_pinned_from_requirement_ab', 'mock_get_raw_requirements_abc',
)
def test_test_dependencies_not_enough_pinned():
    # So we don't skip
    write_file('setup.py', '')
    write_file('requirements.txt', '')
    with pytest.raises(AssertionError) as excinfo:
        main.test_setup_dependencies()
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
        '\tlazy-object-proxy (required by astroid==1.4.3 in requirements-dev.txt)\n'  # noqa
        '\t\tmaybe you want "lazy-object-proxy==1.2.1"?\n'
        '\tmccabe (required by flake8==2.3.0 in requirements.txt)\n'
        '\t\tmaybe you want "mccabe==0.3.1"?\n'
        '\tpep8 (required by flake8==2.3.0 in requirements.txt)\n'
        '\t\tmaybe you want "pep8==1.7.0"?\n'
        '\tpyflakes (required by flake8==2.3.0 in requirements.txt)\n'
        '\t\tmaybe you want "pyflakes==1.0.0"?\n'
        '\tsix (required by astroid==1.4.3 in requirements-dev.txt)\n'
        '\t\tmaybe you want "six==1.10.0"?\n'
        '\twrapt (required by astroid==1.4.3 in requirements-dev.txt)\n'
        '\t\tmaybe you want "wrapt==1.10.6"?',
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


def test_format_versions_on_lines_with_dashes_trivial():
    assert main.format_versions_on_lines_with_dashes(()) == ''


def test_format_versions_on_lines_with_dashes_something():
    versions = ['a', 'b', 'c']
    ret = main.format_versions_on_lines_with_dashes(versions)
    assert ret == (
        '\t- a\n'
        '\t- b\n'
        '\t- c'
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
def test_test_bower_package_versions_no_bower_versions():
    write_file('bower.json', '{"dependencies": {}}')
    # Should not raise
    main.test_bower_package_versions()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_bower_package_versions_matching():
    # TODO: use a dummy package to prevent flake8 upgrade + test breaking
    # Contrived, but let's assume flake8 is a bower package
    write_file('bower.json', '{"dependencies": {"flake8": "2.5.1"}}')
    # Should not raise
    main.test_bower_package_versions()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_bower_package_irrelevant_version():
    # I hope we don't install a python package named jquery any time soon :)
    write_file('bower.json', '{"dependencies": {"jquery": "1.10.0"}}')
    # Should not raise
    main.test_bower_package_versions()


@pytest.mark.usefixtures('in_tmpdir')
def test_test_bower_package_versions_not_matching():
    # TODO: use a dummy package to prevent flake8 upgrade + test breaking
    # Again, contrived, but let's assume flake8 is a bower package
    write_file('bower.json', '{"dependencies": {"flake8": "0.0.0"}}')
    with pytest.raises(AssertionError) as excinfo:
        main.test_bower_package_versions()
    assert excinfo.value.args == (
        'Versions in python do not agree with bower versions:\n'
        'Package: flake8\n'
        'Bower: 0.0.0\n'
        'Python: 2.5.1',
    )
