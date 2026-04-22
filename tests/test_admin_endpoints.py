"""Tests for admin-only endpoint restrictions."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person
from app.security import hash_password


@pytest.mark.asyncio
async def test_admin_can_create_user(client: AsyncClient, db: AsyncSession):
    """Test that admin user can create other users."""
    # Create admin first
    admin_password = "admin_password_123"
    admin_r = await client.post("/auth/login", json={"username": "admin", "password": admin_password})
    assert admin_r.status_code == 200
    admin_token = admin_r.json()["access_token"]
    assert admin_r.json()["user"]["is_admin"] is True

    # Admin creates another user
    create_r = await client.post(
        "/people",
        json={"name": "NewUser", "username": "newuser"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert create_r.status_code == 201
    assert create_r.json()["name"] == "NewUser"


@pytest.mark.asyncio
async def test_normal_user_cannot_create_user(client: AsyncClient, db: AsyncSession):
    """Test that normal user cannot create other users."""
    # Create admin first
    admin_password = "admin_password"
    await client.post("/auth/login", json={"username": "admin", "password": admin_password})

    # Create normal user manually
    normal_password = "normal_password_123"
    person = Person(
        name="NormalUser",
        username="normaluser",
        password_hash=hash_password(normal_password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Normal user tries to create another user
    normal_login = await client.post("/auth/login", json={"username": "normaluser", "password": normal_password})
    normal_token = normal_login.json()["access_token"]

    create_r = await client.post(
        "/people",
        json={"name": "AnotherUser", "username": "anotheruser"},
        headers={"Authorization": f"Bearer {normal_token}"}
    )
    assert create_r.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_update_user(client: AsyncClient, db: AsyncSession):
    """Test that admin user can update other users."""
    # Create admin
    admin_password = "admin_password_123"
    admin_r = await client.post("/auth/login", json={"username": "admin", "password": admin_password})
    admin_token = admin_r.json()["access_token"]

    # Admin creates a user
    create_r = await client.post(
        "/people",
        json={"name": "UserToUpdate", "username": "usertoupdate"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    user_id = create_r.json()["id"]

    # Admin updates the user
    update_r = await client.put(
        f"/people/{user_id}",
        json={"goal_7d": 50},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert update_r.status_code == 200
    assert update_r.json()["goal_7d"] == 50


@pytest.mark.asyncio
async def test_normal_user_cannot_update_user(client: AsyncClient, db: AsyncSession):
    """Test that normal user cannot update other users."""
    # Create admin and normal user
    admin_password = "admin_password"
    await client.post("/auth/login", json={"username": "admin", "password": admin_password})

    normal_password = "normal_password_123"
    person = Person(
        name="NormalUser",
        username="normaluser",
        password_hash=hash_password(normal_password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Create a user to update
    admin_login = await client.post("/auth/login", json={"username": "admin", "password": admin_password})
    admin_token = admin_login.json()["access_token"]

    create_r = await client.post(
        "/people",
        json={"name": "UserToUpdate", "username": "usertoupdate"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    user_id = create_r.json()["id"]

    # Normal user tries to update
    normal_login = await client.post("/auth/login", json={"username": "normaluser", "password": normal_password})
    normal_token = normal_login.json()["access_token"]

    update_r = await client.put(
        f"/people/{user_id}",
        json={"goal_7d": 50},
        headers={"Authorization": f"Bearer {normal_token}"}
    )
    assert update_r.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_delete_user(client: AsyncClient, db: AsyncSession):
    """Test that admin user can delete other users."""
    # Create admin
    admin_password = "admin_password_123"
    admin_r = await client.post("/auth/login", json={"username": "admin", "password": admin_password})
    admin_token = admin_r.json()["access_token"]

    # Admin creates a user
    create_r = await client.post(
        "/people",
        json={"name": "UserToDelete", "username": "usertodelete"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    user_id = create_r.json()["id"]

    # Admin deletes the user
    delete_r = await client.delete(
        f"/people/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert delete_r.status_code == 204


@pytest.mark.asyncio
async def test_normal_user_cannot_delete_user(client: AsyncClient, db: AsyncSession):
    """Test that normal user cannot delete other users."""
    # Create admin and normal user
    admin_password = "admin_password"
    await client.post("/auth/login", json={"username": "admin", "password": admin_password})

    normal_password = "normal_password_123"
    person = Person(
        name="NormalUser",
        username="normaluser",
        password_hash=hash_password(normal_password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Create a user to delete
    admin_login = await client.post("/auth/login", json={"username": "admin", "password": admin_password})
    admin_token = admin_login.json()["access_token"]

    create_r = await client.post(
        "/people",
        json={"name": "UserToDelete", "username": "usertodelete"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    user_id = create_r.json()["id"]

    # Normal user tries to delete
    normal_login = await client.post("/auth/login", json={"username": "normaluser", "password": normal_password})
    normal_token = normal_login.json()["access_token"]

    delete_r = await client.delete(
        f"/people/{user_id}",
        headers={"Authorization": f"Bearer {normal_token}"}
    )
    assert delete_r.status_code == 403


@pytest.mark.asyncio
async def test_any_user_can_list_people(client: AsyncClient, db: AsyncSession):
    """Test that any authenticated user can list people."""
    # Create admin
    admin_password = "admin_password"
    await client.post("/auth/login", json={"username": "admin", "password": admin_password})

    # Create normal user
    normal_password = "normal_password_123"
    person = Person(
        name="NormalUser",
        username="normaluser",
        password_hash=hash_password(normal_password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Normal user can list people
    normal_login = await client.post("/auth/login", json={"username": "normaluser", "password": normal_password})
    normal_token = normal_login.json()["access_token"]

    list_r = await client.get(
        "/people",
        headers={"Authorization": f"Bearer {normal_token}"}
    )
    assert list_r.status_code == 200
    assert len(list_r.json()) > 0
