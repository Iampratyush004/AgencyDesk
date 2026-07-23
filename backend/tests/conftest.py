import pytest
import pytest_asyncio
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db, Base
from app.config import settings

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# SAFETY GUARD: MUST use agencydesk_test
if not settings.DATABASE_URL.endswith("/agencydesk_test"):
    raise RuntimeError(f"Safety Guard Failed: Tests must run against 'agencydesk_test'. Current: {settings.DATABASE_URL}")

@pytest_asyncio.fixture(scope="function")
async def db_session():
    test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
    
    async with TestingSessionLocal() as session:
        # Dependency safe table cleanup
        await session.execute(text(
            "TRUNCATE TABLE "
            "file_approvals, time_entries, files, comments, tasks, "
            "project_memberships, projects, invitations, client_memberships, "
            "clients, agency_memberships, users, agencies "
            "CASCADE;"
        ))
        await session.commit()
        
        yield session
    
    await test_engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def async_client(db_session):
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
