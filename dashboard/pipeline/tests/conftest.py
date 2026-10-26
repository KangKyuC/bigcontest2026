"""Public runs exercise rules and snapshots; integration inputs stay private."""
import pytest
from paths import DATA_ROOT


def pytest_collection_modifyitems(items):
    if (DATA_ROOT/'policy/policy_programs_final.csv').is_file():
        return
    reason='Non-public policy research inputs are absent; see dashboard/README.md'
    for item in items:
        if 'local_data' in item.keywords:
            item.add_marker(pytest.mark.skip(reason=reason))
