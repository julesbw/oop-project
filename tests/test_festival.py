"""Domain and storage tests corresponding to the B2-B4 rules."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from deauville.errors import ConflictError, InvalidValueError, NotFoundError
from deauville.models import Lineup, Performance, Venue
from deauville.utils import slugify


def solo_payload(
    *,
    artist: str = "karim-benali",
    venue: str = "la-cabane",
    start: str = "2027-06-13T08:00",
    duration_minutes: int = 30,
) -> dict[str, object]:
    """Build a valid solo request for rule tests."""
    return {
        "kind": "solo",
        "title": "Morning Coffee",
        "artist": artist,
        "venue": venue,
        "start": start,
        "duration_minutes": duration_minutes,
        "min_age": 0,
        "description": "",
    }


def test_slugify_removes_accents_punctuation_and_extra_spaces() -> None:
    assert slugify("Élodie  Marchal !") == "elodie-marchal"


def test_after_hours_belongs_to_previous_festival_day(festival) -> None:
    performances = festival.programme(day=date(2027, 6, 11))
    assert performances[-1].title == "After Hours"
    assert performances[-1].festival_day == date(2027, 6, 11)


def test_now_returns_current_and_three_upcoming(festival) -> None:
    current, upcoming = festival.now(datetime(2027, 6, 11, 21, 0))
    assert [performance.title for performance in current] == ["Tall Tales"]
    assert [performance.title for performance in upcoming] == [
        "Straight Face",
        "Late Laughs",
        "After Hours",
    ]


def test_unknown_venue_and_artist_are_not_found(festival) -> None:
    with pytest.raises(NotFoundError):
        festival.get_venue("nowhere")
    with pytest.raises(NotFoundError):
        festival.add_performance(solo_payload(artist="nobody"))


def test_venue_needs_thirty_minutes(festival) -> None:
    with pytest.raises(ConflictError, match="Le Kiosque is busy"):
        festival.add_performance(
            solo_payload(
                venue="le-kiosque",
                start="2027-06-12T02:15",
            )
        )


def test_artist_needs_thirty_minutes_even_in_another_venue(festival) -> None:
    with pytest.raises(ConflictError, match="Max Pellerin is on stage"):
        festival.add_performance(
            solo_payload(
                artist="max-pellerin",
                start="2027-06-11T23:00",
            )
        )


def test_duration_and_festival_day_are_checked(festival) -> None:
    with pytest.raises(InvalidValueError):
        festival.add_performance(solo_payload(duration_minutes=0))
    with pytest.raises(ConflictError, match="2027-06-14"):
        festival.add_performance(
            solo_payload(
                start="2027-06-14T08:00",
            )
        )


def test_lineup_rules_are_checked(festival) -> None:
    with pytest.raises(InvalidValueError, match="at least two acts"):
        festival.add_performance(
            {
                "kind": "lineup",
                "title": "Too Small",
                "venue": "la-cabane",
                "start": "2027-06-13T06:00",
                "duration_minutes": 30,
                "host": "tom-vasseur",
                "acts": ["hugo-lemaire"],
            }
        )
    with pytest.raises(InvalidValueError, match="at least 36"):
        Lineup(
            "Too Short",
            festival.get_venue("la-cabane"),
            "2027-06-13T06:00",
            35,
            "tom-vasseur",
            ["hugo-lemaire", "maya-choukri", "sacha-diallo"],
        )


def test_workshop_capacity_and_case_insensitive_registration(festival) -> None:
    workshop = festival.get_performance("la-cabane-2027-06-11-1030")
    assert workshop.capacity == 12
    with pytest.raises(ConflictError, match="already registered"):
        festival.register_participant(workshop.id, "camille r.")

    large = festival.add_performance(
        {
            "kind": "workshop",
            "title": "Large Workshop",
            "venue": "grand-casino",
            "start": "2027-06-13T06:00",
            "duration_minutes": 60,
            "teacher": "sacha-diallo",
            "max_participants": 999,
            "participants": [],
        }
    )
    assert large.capacity == 650


def test_performance_is_abstract() -> None:
    with pytest.raises(TypeError):
        Performance(
            "Show",
            Venue("Room", 10, "Address"),
            "2027-06-13T06:00",
            30,
        )
