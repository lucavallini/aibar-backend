import os
from unittest.mock import MagicMock, patch

os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "test-key"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_EXPIRE_MINUTES"] = "60"

create_client_mock = MagicMock()
patcher = patch("supabase.create_client", create_client_mock)
patcher.start()

import pytest

from app.database import supabase


def _config_query(query_mock):
    for method in ("select", "eq", "in_", "or_", "order", "gte", "lte", "ilike", "range"):
        getattr(query_mock, method).return_value = query_mock


@pytest.fixture(autouse=True)
def mock_supabase_queries():
    query_mock = MagicMock()
    query_mock.execute.return_value = MagicMock(data=[], count=0)
    _config_query(query_mock)

    table_mock = MagicMock()
    table_mock.return_value = query_mock

    supabase.table = table_mock

    yield


@pytest.fixture
def query():
    return supabase.table.return_value


@pytest.fixture
def table():
    return supabase.table
