import os
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="titan-tests-"))
os.environ["TITAN_DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_ROOT / 'test.db'}"
os.environ["TITAN_WORKSPACE_ROOT"] = str(TEST_ROOT / "workspaces")
os.environ["TITAN_REPORT_ROOT"] = str(TEST_ROOT / "reports")
os.environ["TITAN_ENVIRONMENT"] = "development"
os.environ.pop("TITAN_API_KEY", None)

from app.main import app  # noqa: E402


@pytest.fixture
async def client():
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client
