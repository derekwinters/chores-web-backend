import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base
from app.database import get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def seeded_db(db):
    from app.models import Person, Settings

    # Enable auth in tests
    settings = Settings(key="auth_enabled", value="true")
    db.add(settings)

    db.add_all([
        Person(name="Derek", username="derek", password_hash="hash1", is_admin=False),
        Person(name="Amy", username="amy", password_hash="hash2", is_admin=False),
        Person(name="Connor", username="connor", password_hash="hash3", is_admin=False),
        Person(name="Lucas", username="lucas", password_hash="hash4", is_admin=False),
    ])
    await db.commit()
    yield db


@pytest_asyncio.fixture
async def db():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(db):
    from app.security import hash_password

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    # Enable auth in tests
    from app.models import Person, Settings
    settings = Settings(key="auth_enabled", value="true")
    db.add(settings)

    # Create a test user
    test_password = "test_password_123"
    person = Person(
        name="TestUser",
        username="testuser",
        password_hash=hash_password(test_password),
        is_admin=True
    )
    db.add(person)
    await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login and get token
        login_r = await ac.post("/auth/login", json={"username": "testuser", "password": test_password})
        token = login_r.json()["access_token"]

        # Add token to default headers
        ac.headers = {"Authorization": f"Bearer {token}"}

        yield ac
    app.dependency_overrides.clear()
