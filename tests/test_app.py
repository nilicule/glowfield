from datetime import date

from fastapi.testclient import TestClient

from glowfield.app import app, daily_seed

client = TestClient(app)


def test_puzzle_endpoint_is_deterministic_by_seed():
    a = client.get("/api/puzzle", params={"difficulty": "easy", "seed": 12}).json()
    b = client.get("/api/puzzle", params={"difficulty": "easy", "seed": 12}).json()
    assert a == b
    assert a["id"] == "easy-12"
    assert a["rows"] == 7


def test_unknown_difficulty_404():
    assert client.get("/api/puzzle", params={"difficulty": "nope"}).status_code == 404


def test_daily():
    data = client.get("/api/daily").json()
    assert data["daily"] == date.today().isoformat()
    assert data["difficulty"] == "medium"
    assert data["seed"] == daily_seed(date.today())


def test_daily_board_cannot_be_loaded_as_a_normal_puzzle():
    seed = daily_seed(date.today())
    r = client.get("/api/puzzle", params={"difficulty": "medium", "seed": seed})
    assert r.status_code == 400


def test_server_sets_no_cookies():
    for path in ("/", "/api/daily", "/api/puzzle"):
        assert not client.get(path).cookies


def test_hint():
    p = client.get("/api/puzzle", params={"difficulty": "beginner", "seed": 1}).json()
    h = client.post("/api/hint", json={"difficulty": "beginner", "seed": 1}).json()
    flies = {tuple(c) for c in p["fireflies"]}
    assert h["reason"]
    for cell in h["cells"]:
        assert (tuple(cell) in flies) == h["firefly"]


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200 and "Glowfield" in r.text
