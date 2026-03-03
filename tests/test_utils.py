"""Tests for pipeline.utils — shared DB and H3 helper functions.

Tests are split into two tiers:
  - Pure logic (to_python, bulk_insert with mock cursor)
  - DB-dependent (get_db_connection, table_row_count) — patched
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ── to_python() ─────────────────────────────────────────────


class TestToPython:
    """to_python converts numpy/pandas scalars to native Python
    so psycopg2 can adapt them."""

    def test_numpy_int64(self):
        from pipeline.utils import to_python

        assert to_python(np.int64(42)) == 42
        assert isinstance(to_python(np.int64(42)), int)

    def test_numpy_float64(self):
        from pipeline.utils import to_python

        assert to_python(np.float64(3.14)) == pytest.approx(3.14)
        assert isinstance(to_python(np.float64(3.14)), float)

    def test_numpy_bool(self):
        from pipeline.utils import to_python

        assert to_python(np.bool_(True)) is True

    def test_native_int_passthrough(self):
        from pipeline.utils import to_python

        assert to_python(42) == 42
        assert isinstance(to_python(42), int)

    def test_native_str_passthrough(self):
        from pipeline.utils import to_python

        assert to_python("hello") == "hello"

    def test_none_passthrough(self):
        from pipeline.utils import to_python

        assert to_python(None) is None

    def test_pandas_nat(self):
        from pipeline.utils import to_python

        assert to_python(pd.NaT) is None

    def test_numpy_nan(self):
        from pipeline.utils import to_python

        assert to_python(np.nan) is None

    def test_pandas_na(self):
        from pipeline.utils import to_python

        assert to_python(pd.NA) is None

    def test_numpy_float32(self):
        from pipeline.utils import to_python

        result = to_python(np.float32(1.5))
        assert isinstance(result, float)
        assert result == pytest.approx(1.5, rel=1e-5)


# ── bulk_insert() ───────────────────────────────────────────


class TestBulkInsert:
    def test_inserts_all_rows(self):
        from pipeline.utils import bulk_insert

        mock_cur = MagicMock()
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})

        with patch("pipeline.utils.execute_values") as mock_ev:
            count = bulk_insert(mock_cur, "test_table", df, batch_size=10)
        assert count == 3
        assert mock_ev.call_count == 1
        # Verify SQL contains table and column names
        sql_arg = mock_ev.call_args[0][1]
        assert "test_table" in sql_arg
        assert "a" in sql_arg and "b" in sql_arg

    def test_batching(self):
        from pipeline.utils import bulk_insert

        mock_cur = MagicMock()
        df = pd.DataFrame({"x": list(range(25))})

        with patch("pipeline.utils.execute_values") as mock_ev:
            count = bulk_insert(mock_cur, "tbl", df, batch_size=10)
        assert count == 25
        # 25 rows / 10 per batch = 3 calls
        assert mock_ev.call_count == 3

    def test_empty_dataframe(self):
        from pipeline.utils import bulk_insert

        mock_cur = MagicMock()
        df = pd.DataFrame({"a": []})

        count = bulk_insert(mock_cur, "tbl", df)
        assert count == 0

    def test_converts_numpy_types(self):
        """Ensures numpy types go through to_python conversion."""
        from pipeline.utils import bulk_insert

        mock_cur = MagicMock()
        df = pd.DataFrame(
            {
                "int_col": np.array([1, 2], dtype=np.int64),
                "float_col": np.array([1.1, 2.2], dtype=np.float64),
            }
        )

        with patch("pipeline.utils.execute_values") as mock_ev:
            count = bulk_insert(mock_cur, "tbl", df, batch_size=100)
        assert count == 2
        # Verify records were converted to native Python types
        records = mock_ev.call_args[0][2]
        for row in records:
            for val in row:
                assert not isinstance(val, (np.generic,))


# ── get_db_connection() ─────────────────────────────────────


class TestGetDbConnection:
    def test_commits_on_success(self):
        from pipeline.utils import get_db_connection

        mock_conn = MagicMock()
        with (
            patch(
                "pipeline.utils.psycopg2.connect",
                return_value=mock_conn,
            ),
            get_db_connection() as conn,
        ):
            conn.cursor()

        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()
        mock_conn.rollback.assert_not_called()

    def test_rolls_back_on_exception(self):
        from pipeline.utils import get_db_connection

        mock_conn = MagicMock()
        with (
            patch(
                "pipeline.utils.psycopg2.connect",
                return_value=mock_conn,
            ),
            pytest.raises(ValueError),
            get_db_connection(),
        ):
            raise ValueError("boom")

        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()
        mock_conn.commit.assert_not_called()

    def test_autocommit_mode(self):
        from pipeline.utils import get_db_connection

        mock_conn = MagicMock()
        with (
            patch(
                "pipeline.utils.psycopg2.connect",
                return_value=mock_conn,
            ),
            get_db_connection(autocommit=True),
        ):
            pass

        # autocommit mode: no explicit commit or rollback
        mock_conn.commit.assert_not_called()
        mock_conn.rollback.assert_not_called()
        mock_conn.close.assert_called_once()


# ── table_row_count() ───────────────────────────────────────


class TestTableRowCount:
    def test_returns_count(self):
        from pipeline.utils import table_row_count

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (42,)

        with patch(
            "pipeline.utils.psycopg2.connect",
            return_value=mock_conn,
        ):
            assert table_row_count("some_table") == 42


# ── patch_shap_for_xgboost3() ──────────────────────────────


class TestPatchShap:
    def test_idempotent(self):
        """Calling patch twice should not double-wrap."""
        from pipeline.utils import patch_shap_for_xgboost3

        patch_shap_for_xgboost3()
        patch_shap_for_xgboost3()  # second call is a no-op

        import shap.explainers._tree as _tree_mod

        assert getattr(_tree_mod.decode_ubjson_buffer, "_xgb3_patched", False)

    def test_strips_brackets(self):
        """The patched decode should strip [] from learner_model_param."""
        from pipeline.utils import patch_shap_for_xgboost3

        patch_shap_for_xgboost3()

        import shap.explainers._tree as _tree_mod

        # Verify the patched function is callable and marked
        patched_fn = _tree_mod.decode_ubjson_buffer
        assert callable(patched_fn)
        assert getattr(patched_fn, "_xgb3_patched", False)
