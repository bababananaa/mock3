def book(client, **overrides):
    payload = {
        "walker_id": 2,
        "dog_id": 1,
        "start_time": "2026-09-20T10:00",
        "duration_minutes": 30,
    }
    payload.update(overrides)
    return client.post("/walks", json=payload)


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_list_walkers_hides_inactive(client):
    names = [walker["name"] for walker in client.get("/walkers").get_json()]
    assert "Sam Okafor" not in names
    assert len(names) == 3


def test_create_walk(client):
    response = book(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] == 15
    assert body["price_cents"] == 1000
    assert body["status"] == "scheduled"


def test_large_dog_surcharge(client):
    response = book(client, walker_id=1, dog_id=3, start_time="2026-09-22T08:00", duration_minutes=60)
    assert response.get_json()["price_cents"] == 2900


def test_missing_fields(client):
    response = client.post("/walks", json={"walker_id": 1})
    assert response.status_code == 400


def test_non_json_body(client):
    response = client.post("/walks", data="walker_id=1")
    assert response.status_code == 400


def test_unknown_dog(client):
    assert book(client, dog_id=99).status_code == 404


def test_inactive_walker(client):
    assert book(client, walker_id=3).status_code == 409


def test_invalid_duration(client):
    assert book(client, duration_minutes=45).status_code == 400


def test_start_time_in_past(client):
    assert book(client, start_time="2026-09-01T10:00").status_code == 400


def test_walker_fully_booked(client):
    response = book(client, walker_id=4, start_time="2026-09-18T10:30")
    assert response.status_code == 409


def test_cancel_walk(client):
    first = client.post("/walks/12/cancel")
    assert first.status_code == 200
    assert first.get_json()["status"] == "cancelled"
    assert client.post("/walks/12/cancel").status_code == 409


def test_cancel_completed_walk(client):
    assert client.post("/walks/1/cancel").status_code == 409
