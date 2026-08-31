from kflow.core.query import QUERY_SCHEMA_VERSION
from kflow.core.storage import SCHEMA_VERSION


def test_query_schema_bump_does_not_change_git_metadata_schema() -> None:
    assert QUERY_SCHEMA_VERSION == 3
    assert SCHEMA_VERSION == 2
