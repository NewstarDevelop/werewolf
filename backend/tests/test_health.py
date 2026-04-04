import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_register(client):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "securepass123",
            "nickname": "TestUser",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["nickname"] == "TestUser"


@pytest.mark.asyncio
async def test_register_duplicate(client):
    body = {"email": "dup@example.com", "password": "securepass123", "nickname": "DupUser"}
    r1 = await client.post("/api/auth/register", json=body)
    assert r1.status_code == 201

    r2 = await client.post("/api/auth/register", json=body)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_login(client):
    await client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "mypass123", "nickname": "LoginUser"},
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "mypass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "login@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/api/auth/register",
        json={"email": "wrong@example.com", "password": "correct123", "nickname": "WrongUser"},
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": "wrong@example.com", "password": "incorrect123"},
    )
    assert response.status_code == 401
