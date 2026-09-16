from datetime import datetime

import pytest

from app import create_app
from storage.csv_store import CsvStore

collect_ignore = ["pr_review"]


@pytest.fixture
def client():
    app = create_app(store=CsvStore(), clock=lambda: datetime(2026, 9, 16, 9, 0))
    app.config["TESTING"] = True
    return app.test_client()
