"""HTTP contract tests corresponding to API.md."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_read_routes(client: TestClient) -> None:
    festival = client.get("/api/festival")
    assert festival.status_code == 200
    assert festival.json()["days"] == [
        "2027-06-10",
        "2027-06-11",
        "2027-06-12",
        "2027-06-13",
    ]

    venues = client.get("/api/venues").json()
    assert [venue["slug"] for venue in venues] == [
        "grand-casino",
        "theatre-des-planches",
        "le-kiosque",
        "la-cabane",
    ]
    artists = client.get("/api/artists").json()
    assert artists[0]["slug"] == "elodie-marchal"

    programme = client.get(
        "/api/programme",
        params={"day": "2027-06-11", "venue": "le-kiosque"},
    )
    assert programme.status_code == 200
    assert [item["title"] for item in programme.json()] == [
        "Writing a Punchline",
        "Late Laughs",
        "After Hours",
    ]


def test_performance_and_artist_views(client: TestClient) -> None:
    performance = client.get("/api/performances/le-kiosque-2027-06-12-0100")
    assert performance.status_code == 200
    assert performance.json()["festival_day"] == "2027-06-11"
    assert performance.json()["summary"].startswith("hosted by Tom Vasseur")

    artist = client.get("/api/artists/max-pellerin")
    assert artist.status_code == 200
    assert len(artist.json()["performances"]) == 4


def test_now_and_validation_statuses(client: TestClient) -> None:
    now = client.get("/api/now", params={"at": "2027-06-11T21:00"})
    assert now.status_code == 200
    assert now.json()["now_playing"][0]["title"] == "Tall Tales"
    assert len(now.json()["up_next"]) == 3

    assert client.get("/api/artists/nobody").status_code == 404
    assert client.get("/api/programme", params={"day": "June 11"}).status_code == 422

    incomplete = client.post(
        "/api/performances",
        json={
            "kind": "solo",
            "title": "Incomplete",
            "venue": "le-kiosque",
            "start": "2027-06-13T06:00",
            "duration_minutes": 30,
        },
    )
    assert incomplete.status_code == 422


def test_write_routes_and_duplicate_artist(client: TestClient) -> None:
    artist = client.post("/api/artists", json={"name": "Zoé Tanguy"})
    assert artist.status_code == 201
    assert artist.json()["slug"] == "zoe-tanguy"

    duplicate = client.post("/api/artists", json={"name": "zoe tanguy"})
    assert duplicate.status_code == 409

    performance = client.post(
        "/api/performances",
        json={
            "kind": "solo",
            "title": "Morning Coffee",
            "venue": "le-kiosque",
            "start": "2027-06-13T11:00",
            "duration_minutes": 45,
            "artist": "zoe-tanguy",
            "min_age": 0,
        },
    )
    assert performance.status_code == 201
    assert performance.json()["id"] == "le-kiosque-2027-06-13-1100"


def test_refused_update_keeps_the_original_performance(client: TestClient) -> None:
    created = client.post(
        "/api/performances",
        json={
            "kind": "solo",
            "title": "Morning Coffee",
            "venue": "le-kiosque",
            "start": "2027-06-13T11:00",
            "duration_minutes": 45,
            "artist": "sacha-diallo",
            "min_age": 0,
        },
    )
    performance_id = created.json()["id"]
    refused = client.put(
        f"/api/performances/{performance_id}",
        json={
            "kind": "solo",
            "title": "Morning Coffee",
            "venue": "le-kiosque",
            "start": "2027-06-13T15:00",
            "duration_minutes": 45,
            "artist": "sacha-diallo",
            "min_age": 0,
        },
    )
    assert refused.status_code == 409
    assert client.get(f"/api/performances/{performance_id}").status_code == 200


def test_workshop_registration_and_delete(client: TestClient) -> None:
    workshop_id = "la-cabane-2027-06-11-1030"
    registered = client.post(
        f"/api/performances/{workshop_id}/participants",
        json={"name": "New Participant"},
    )
    assert registered.status_code == 201
    duplicate = client.post(
        f"/api/performances/{workshop_id}/participants",
        json={"name": "new participant"},
    )
    assert duplicate.status_code == 409

    deleted = client.delete("/api/performances/le-kiosque-2027-06-12-0100")
    assert deleted.status_code == 204
    deleted_again = client.delete("/api/performances/le-kiosque-2027-06-12-0100")
    assert deleted_again.status_code == 404


def test_workshop_update_preserves_participants_when_omitted(
    client: TestClient,
) -> None:
    workshop_id = "la-cabane-2027-06-11-1030"
    updated = client.put(
        f"/api/performances/{workshop_id}",
        json={
            "kind": "workshop",
            "title": "Improv for Beginners Updated",
            "venue": "la-cabane",
            "start": "2027-06-11T10:30",
            "duration_minutes": 120,
            "teacher": "ines-moreau",
            "max_participants": 12,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["participants"] == [
        "Camille R.",
        "Yanis B.",
        "Lou M.",
    ]


def test_storage_error_is_a_500(tmp_path: Path) -> None:
    from deauville.api import create_app
    from deauville.storage import JsonStorage

    missing = tmp_path / "missing.json"
    response = TestClient(create_app(JsonStorage(missing))).get("/api/festival")
    assert response.status_code == 500
