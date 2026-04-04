import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def authed_user(client):
    res = await client.post(
        "/api/auth/register",
        json={"email": "room@test.com", "password": "testpass123", "nickname": "RoomTester"},
    )
    assert res.status_code == 201
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_user(client):
    res = await client.post(
        "/api/auth/register",
        json={"email": "room2@test.com", "password": "testpass123", "nickname": "Player2"},
    )
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def created_room(client, authed_user):
    res = await client.post(
        "/api/rooms/",
        json={"name": "Test Room", "mode": "classic_9"},
        headers=authed_user,
    )
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.asyncio
async def test_create_room(client, authed_user):
    res = await client.post(
        "/api/rooms/",
        json={"name": "Test Room", "mode": "classic_9"},
        headers=authed_user,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Test Room"
    assert data["mode"] == "classic_9"
    assert data["max_players"] == 9
    assert data["status"] == "waiting"
    assert len(data["players"]) == 1
    assert data["players"][0]["is_ready"] is True


@pytest.mark.asyncio
async def test_list_rooms(client, authed_user):
    await client.post(
        "/api/rooms/",
        json={"name": "Visible Room", "mode": "classic_9"},
        headers=authed_user,
    )

    # List rooms is public (no auth needed)
    res = await client.get("/api/rooms/")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(r["name"] == "Visible Room" for r in data["items"])


@pytest.mark.asyncio
async def test_join_room(client, authed_user, second_user, created_room):
    res = await client.post(f"/api/rooms/{created_room}/join", headers=second_user)
    assert res.status_code == 200
    assert len(res.json()["players"]) == 2


@pytest.mark.asyncio
async def test_join_room_idempotent(client, second_user, created_room):
    await client.post(f"/api/rooms/{created_room}/join", headers=second_user)
    res = await client.post(f"/api/rooms/{created_room}/join", headers=second_user)
    assert res.status_code == 400
    assert "Already" in res.json()["detail"]


@pytest.mark.asyncio
async def test_leave_room(client, second_user, created_room):
    await client.post(f"/api/rooms/{created_room}/join", headers=second_user)
    res = await client.post(f"/api/rooms/{created_room}/leave", headers=second_user)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_owner_cannot_leave(client, authed_user, created_room):
    res = await client.post(f"/api/rooms/{created_room}/leave", headers=authed_user)
    assert res.status_code == 403 or res.status_code == 400
    detail = res.json()["detail"]
    assert "Owner" in detail or "owner" in detail


@pytest.mark.asyncio
async def test_toggle_ready(client, second_user, created_room):
    await client.post(f"/api/rooms/{created_room}/join", headers=second_user)
    res = await client.post(f"/api/rooms/{created_room}/ready", headers=second_user)
    assert res.status_code == 200
    assert res.json()["is_ready"] is True

    res2 = await client.post(f"/api/rooms/{created_room}/ready", headers=second_user)
    assert res2.json()["is_ready"] is False


@pytest.mark.asyncio
async def test_fill_ai(client, authed_user, created_room):
    res = await client.post(
        f"/api/rooms/{created_room}/fill-ai",
        json={"count": 8},
        headers=authed_user,
    )
    assert res.status_code == 200
    data = res.json()
    # 1 owner + 8 AI = 9 total
    assert len(data["players"]) == 9


@pytest.mark.asyncio
async def test_delete_room(client, authed_user, second_user):
    r = await client.post(
        "/api/rooms/", json={"name": "Del", "mode": "classic_9"}, headers=authed_user
    )
    room_id = r.json()["id"]

    res = await client.delete(f"/api/rooms/{room_id}", headers=second_user)
    assert res.status_code == 403

    res = await client.delete(f"/api/rooms/{room_id}", headers=authed_user)
    assert res.status_code == 200
