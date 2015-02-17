from __future__ import absolute_import
from __future__ import unicode_literals

import os.path

# pylint:disable=unused-argument

HERE = os.path.abspath(os.path.dirname(__file__))


def pytest_collection_modifyitems(session, config, items):
    mod = session.ihook.pytest_pycollect_makemodule(
        path=os.path.join(HERE, 'checks.py'), parent=session,
    )
    items.extend(mod.collect())
