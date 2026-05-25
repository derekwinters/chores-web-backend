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
    from datetime import datetime, timedelta, timezone
    from app.models import Chore, Person, PointsLog, Settings
    from app.security import hash_password

    # Enable auth in tests
    settings = Settings(key="auth_enabled", value="true")
    db.add(settings)

    db.add_all([
        Person(name="Derek", username="derek", password_hash=hash_password("derek_pass"), is_admin=True),
        Person(name="Amy", username="amy", password_hash="hash2", is_admin=False),
        Person(name="Connor", username="connor", password_hash="hash3", is_admin=False),
        Person(name="Lucas", username="lucas", password_hash="hash4", is_admin=False),
    ])
    await db.commit()

    # Add one Chore so seeded_client tests can reference a real chore
    chore = Chore(
        name="Seeded Chore",
        schedule_type="interval",
        schedule_config={"days": 7},
        assignment_type="open",
        eligible_people=[],
        points=10,
    )
    db.add(chore)
    await db.commit()

    # Add two PointsLog entries for derek: 3d ago = 10pts, 15d ago = 20pts
    now = datetime.now(timezone.utc)
    db.add_all([
        PointsLog(person="derek", chore_id=chore.id, points=10, completed_at=now - timedelta(days=3)),
        PointsLog(person="derek", chore_id=chore.id, points=20, completed_at=now - timedelta(days=15)),
    ])
    await db.commit()

    yield db


@pytest_asyncio.fixture
async def seeded_client(seeded_db):
    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login_r = await ac.post("/auth/login", json={"username": "derek", "password": "derek_pass"})
        token = login_r.json()["access_token"]
        ac.headers = {"Authorization": f"Bearer {token}"}
        yield ac, seeded_db

    app.dependency_overrides.clear()


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
