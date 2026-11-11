import pytest
from sqlalchemy import inspect

from parley.evals.database import EVAL_SUFFIX, eval_database_url, recreate_eval_database


def test_eval_url_points_at_a_separate_database() -> None:
    assert eval_database_url().rsplit("/", 1)[1].endswith(EVAL_SUFFIX)


def test_recreating_a_database_without_the_suffix_is_refused() -> None:
    with pytest.raises(ValueError, match="refusing"):
        recreate_eval_database("postgresql://u:p@localhost:5432/parley")


def test_recreated_database_has_the_schema() -> None:
    engine = recreate_eval_database()
    try:
        assert {"customers", "orders", "refunds", "chunks"} <= set(
            inspect(engine).get_table_names()
        )
    finally:
        engine.dispose()
