requirements-tools
========

[![PyPI version](https://badge.fury.io/py/requirements-tools.svg)](https://pypi.python.org/pypi/requirements-tools)
[![Build Status](https://github.com/Yelp/requirements-tools/workflows/build/badge.svg?branch=master)](https://github.com/Yelp/requirements-tools/actions?query=workflow%3Abuild)

requirements-tools contains scripts for working with Python requirements,
primarily in applications.

It consists of three scripts:

  * `check-requirements`
  * `upgrade-requirements`
  * `visualize-requirements`

These are discussed in detail below.


## Our stance on pinning requirements

In applications, you want to ensure repeatable builds. It's important that the
version of code you tested with is the same version that goes to production,
and that upgrades of third-party packages don't break your application. Since
each commit represents a precise deployment (code and its dependencies), you
can always easily see what changed between two deployments, and count on being
able to revert changes.

By contrast, in libraries, you want to maximize compatibility and know about
incompatibilities with other libraries as soon as possible. In libraries the
best practices is to only loosely pin requirements, and only when absolutely
necessary.


### Recommended requirements setup for applications

The recommended layout for your application is:

* No `setup.py`.  `setup.py` is not entirely useful for applications, we'll
  specify minimal requirements in `requirements-minimal.txt` (see below).
  (Some applications have special needs for a `setup.py`, and that's fine—but
  we won't use them for listing requirements).

* `requirements-minimal.txt` contains a list of unpinned (or loosely-pinned)
  top-level requirements needed in production. For example, you might list
  `requests`, but you wouldn't list libraries `requests` depends on.

  If you know of a problematic version, you should *loosely* pin here (e.g.
  `requests>=4` if you know you depend on APIs introduced in version 4).

* `requirements-dev-minimal.txt` is much like `requirements-minimal.txt`, but
  is intended for dev dependencies. You should list loosely-pinned top-level
  dependencies only.

* `requirements.txt` contains a list of all production dependencies (and
  sub-dependencies) with strict pinning. When deploying your app, you install
  dependencies from this file, not `requirements-minimal.txt`.

  The benefits to strict pinning are more deterministic versioning (you can
  roll back more easily) and faster virtualenv generation with
  [pip-faster](https://github.com/Yelp/pip-faster).

  In principle, it is possible to automatically generate `requirements.txt` by
  creating a fresh virtualenv, installing your app's dependencies from
  `requirements-minimal.txt`, and running `pip freeze`. We provide a script
  `upgrade-requirements` which effectively does this (but better handling some
  edge cases).

* `requirements-dev.txt` is just like `requirements.txt` but for dev
  dependencies (and dev sub-dependencies).

  It could be automatically generated by creating a fresh virtualenv,
  installing the requirements listed in `requirements-dev-minimal.txt`, running
  `pip freeze`, and subtracting out common requirements already in
  `requirements.txt`.

All of these files should be checked into your application.


## check-requirements

check-requirements tests for problems with requirements. It's intended to be
run as part of your application's tests.

If your application passes check-requirements, then you have a high degree of
assurance that it correctly and fully pins its requirements.


### What it does

* Checks for requirements listed in `requirements.txt` but not
  `requirements-minimal.txt` (probably indicates unused requirements or used
  requirements that need to be added to `requirements-minimal.txt`).

* Checks for requirements in `requirements-minimal.txt` but not in
  `requirements.txt` (generally referred to "unpinned" requirements.)

* Checks that package names are properly normalized (e.g. using dashes instead
  of underscores)

* Checks for unpinned requirements or loosely-pinned requirements


### Adding `check-requirements` to your tests

You should run the executable `check-requirements` in a virtualenv with the
`requirements.txt` and `requirements-dev.txt` installed as part of your
tests.

If you're using `tox`, you can just add it to the end of `commands` and add
`requirements-tools` to your dev requirements file (probably
`requirements-dev.txt`).


## upgrade-requirements

upgrade-requirements uses the requirements structure described above in order
to upgrade both dev and prod dependencies while pruning no-longer-needed
dependencies and automatically pinning any added dependencies.

To use upgrade-requirements, install `requirements-tools` into your virtualenv
(you probably already have this, if you're using check-requirements) and run
`upgrade-requirements`.

If your project doesn't use the public PyPI, you can set the PyPI server using
the option `-i https://pypi.example.com/simple`.


## visualize-requirements

visualize-requirements prints a visual representation of your requirements,
making it easy to see why a certain package is being installed (what depends on
it).

To use it, just call `visualize-requirements requirements.txt`.

## check-all-wheels

This tool checks whether all of your dependencies are pre-wheeled on the
remote pypi server.  This is useful while upgrading requirements to verify
that you won't waste time building things from source during installation.

### Checking against an internal pypi server

This script is most useful if you run an internal pypi server and pass the
`--index-url` argument.

```bash
check-all-wheels --index-url https://pypi.example.com/simple
```

### With `pip-custom-platform`

See [asottile/pip-custom-platform](https://github.com/asottile/pip-custom-platform)
for more details.

```
# Check that all prebuilt wheels exist on ubuntu xenial
check-all-wheels \
    --index-url https://pypi.example.com/simple \
    --install-deps pip-custom-platform \
    --pip-tool 'pip-custom-platform --platform linux_ubuntu_16_04_x86_64'
```
