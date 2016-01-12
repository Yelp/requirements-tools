check-requirements
========

check-requirements tests for problems with requirements. It's intended to be
run as part of your project's tests.


## What it does

* Checks for requirements listed in `requirements.txt` but not `setup.py`
  (probably indicates unused requirements or used requirements that need to be
  added to `setup.py`)

* Checks for requirements in `setup.py` but not in `requirements.txt`

* Checks for consistency between `requirements.txt` and `bower.json` (if one
  exists)

* Checks for dashes instead of underscores in requirement names

* Checks for unpinned requirements or loosely-pinned requirements


## Adding to your project

You should run the executable `check-requirements` in a virtualenv with the
`check-requirements` package installed as part of your tests.

If you're using `tox`, you can just add it to the end of `commands` and add
`check-requirements` to your dev requirements file (probably
`requirements-dev.txt`).
