from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db import database as db_module


@pytest_asyncio.fixture(autouse=True)
async def setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    await db_module.init_db(db_path)
    yield
    await db_module.close_db()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
