"""Domain objects for venues, artists and the three performance kinds."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, ClassVar

from .errors import ConflictError, InvalidValueError
from .utils import clean_name, clean_optional_text, parse_local_datetime, slugify


@dataclass(frozen=True, slots=True)
class Venue:
    """A festival venue, identified by the slug of its name."""

    name: str
    capacity: int
    address: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", clean_name(self.name, "Venue name"))
        if (
            isinstance(self.capacity, bool)
            or not isinstance(self.capacity, int)
            or self.capacity < 1
        ):
            raise InvalidValueError("A venue needs at least one seat.")
        object.__setattr__(self, "address", clean_name(self.address, "Venue address"))

    @property
    def slug(self) -> str:
        """Return the stable identifier derived from the venue name."""
        return slugify(self.name, "Venue name")

    def to_view(self) -> dict[str, Any]:
        """Return the public representation used by the API."""
        return {
            "slug": self.slug,
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }

    def to_record(self) -> dict[str, Any]:
        """Return the JSON representation stored on disk."""
        return {
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }


@dataclass(frozen=True, slots=True)
class Artist:
    """An artist, identified by the slug of their name."""

    name: str
    bio: str = ""
    photo_url: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", clean_name(self.name, "Artist name"))
        object.__setattr__(self, "bio", clean_optional_text(self.bio))
        object.__setattr__(self, "photo_url", clean_optional_text(self.photo_url))

    @property
    def slug(self) -> str:
        """Return the stable identifier derived from the artist name."""
        return slugify(self.name, "Artist name")

    def to_view(self) -> dict[str, Any]:
        """Return the public representation used by the API."""
        return {
            "slug": self.slug,
            "name": self.name,
            "bio": self.bio,
            "photo_url": self.photo_url,
        }

    def to_record(self) -> dict[str, Any]:
        """Return the JSON representation stored on disk."""
        return {
            "name": self.name,
            "bio": self.bio,
            "photo_url": self.photo_url,
        }


class Performance(ABC):
    """Common behaviour shared by every kind of performance."""

    kind: ClassVar[str]

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime | str,
        duration_minutes: int,
        description: str = "",
    ) -> None:
        self.title = clean_name(title, "Performance title")
        if not isinstance(venue, Venue):
            raise InvalidValueError("A performance needs a valid venue.")
        self.venue = venue
        self.start = parse_local_datetime(start)
        if (
            isinstance(duration_minutes, bool)
            or not isinstance(duration_minutes, int)
            or not 1 <= duration_minutes <= 360
        ):
            raise InvalidValueError(
                "A performance must last between 1 and 360 minutes."
            )
        self.duration_minutes = duration_minutes
        self.description = clean_optional_text(description)

    @property
    def id(self) -> str:
        """Return the stable identifier made from venue and start."""
        return f"{self.venue.slug}-{self.start:%Y-%m-%d-%H%M}"

    @property
    def end(self) -> datetime:
        """Return the moment at which the performance ends."""
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def festival_day(self) -> date:
        """Return the programme day; the festival night ends at 06:00."""
        return (self.start - timedelta(hours=6)).date()

    @property
    def capacity(self) -> int:
        """Return the number of available seats or places."""
        return self.venue.capacity

    @abstractmethod
    def artist_slugs(self) -> tuple[str, ...]:
        """Return every artist on stage, in appearance order."""

    @abstractmethod
    def role_for(self, artist_slug: str) -> str | None:
        """Return the artist's role in this performance."""

    @abstractmethod
    def summary(self, artists: Mapping[str, Artist]) -> str:
        """Return the one-line programme summary."""

    @abstractmethod
    def specific_view(self, artists: Mapping[str, Artist]) -> dict[str, Any]:
        """Return fields specific to the performance kind."""

    @abstractmethod
    def specific_record(self) -> dict[str, Any]:
        """Return fields specific to the stored JSON record."""

    def to_view(self, artists: Mapping[str, Artist]) -> dict[str, Any]:
        """Return the complete API representation."""
        artist_views = [
            {"slug": slug, "name": artists[slug].name} for slug in self.artist_slugs()
        ]
        result = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "venue_name": self.venue.name,
            "start": self.start.isoformat(timespec="minutes"),
            "end": self.end.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "festival_day": self.festival_day.isoformat(),
            "description": self.description,
            "summary": self.summary(artists),
            "capacity": self.capacity,
            "artists": artist_views,
        }
        result.update(self.specific_view(artists))
        return result

    def to_record(self) -> dict[str, Any]:
        """Return the saved fields for this performance."""
        result = {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "start": self.start.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }
        result.update(self.specific_record())
        return result

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Performance):
            return NotImplemented
        return (self.start, self.venue.name.casefold()) < (
            other.start,
            other.venue.name.casefold(),
        )


class SoloShow(Performance):
    """A performance featuring one artist."""

    kind = "solo"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime | str,
        duration_minutes: int,
        artist: str,
        min_age: int,
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        self.artist = slugify(artist, "Artist")
        if (
            isinstance(min_age, bool)
            or not isinstance(min_age, int)
            or not 0 <= min_age <= 18
        ):
            raise InvalidValueError("The minimum age must be between 0 and 18.")
        self.min_age = min_age

    def artist_slugs(self) -> tuple[str, ...]:
        return (self.artist,)

    def role_for(self, artist_slug: str) -> str | None:
        return "solo" if artist_slug == self.artist else None

    def summary(self, artists: Mapping[str, Artist]) -> str:
        return artists[self.artist].name

    def specific_view(self, artists: Mapping[str, Artist]) -> dict[str, Any]:
        return {"artist": self.artist, "min_age": self.min_age}

    def specific_record(self) -> dict[str, Any]:
        return {"artist": self.artist, "min_age": self.min_age}


class Lineup(Performance):
    """A host introducing a sequence of acts."""

    kind = "lineup"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime | str,
        duration_minutes: int,
        host: str,
        acts: list[str] | tuple[str, ...],
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        self.host = slugify(host, "Host")
        if isinstance(acts, (str, bytes)) or not isinstance(acts, (list, tuple)):
            raise InvalidValueError("A lineup needs a list of acts.")
        self.acts = tuple(slugify(act, "Act") for act in acts)
        if len(self.acts) < 2:
            raise InvalidValueError("A lineup needs at least two acts.")
        if len(set(self.acts)) != len(self.acts):
            raise InvalidValueError("A lineup cannot repeat an act.")
        if self.host in self.acts:
            raise InvalidValueError("The host cannot also be an act.")
        minimum = len(self.acts) * 10 + (len(self.acts) - 1) * 3
        if self.duration_minutes < minimum:
            raise InvalidValueError(
                f"A lineup with {len(self.acts)} acts needs at least {minimum} minutes."
            )

    def artist_slugs(self) -> tuple[str, ...]:
        return (self.host, *self.acts)

    def role_for(self, artist_slug: str) -> str | None:
        if artist_slug == self.host:
            return "host"
        if artist_slug in self.acts:
            return "act"
        return None

    def summary(self, artists: Mapping[str, Artist]) -> str:
        names = ", ".join(artists[slug].name for slug in self.acts)
        return f"hosted by {artists[self.host].name}, with {names}"

    def specific_view(self, artists: Mapping[str, Artist]) -> dict[str, Any]:
        return {"host": self.host, "acts": list(self.acts)}

    def specific_record(self) -> dict[str, Any]:
        return {"host": self.host, "acts": list(self.acts)}


class Workshop(Performance):
    """A teacher-led workshop with case-insensitive registration."""

    kind = "workshop"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime | str,
        duration_minutes: int,
        teacher: str,
        max_participants: int,
        participants: list[str] | tuple[str, ...] | None = None,
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        self.teacher = slugify(teacher, "Teacher")
        if (
            isinstance(max_participants, bool)
            or not isinstance(max_participants, int)
            or max_participants < 1
        ):
            raise InvalidValueError("A workshop needs at least one place.")
        self.max_participants = max_participants
        if participants is None:
            participants = []
        if isinstance(participants, (str, bytes)) or not isinstance(
            participants, (list, tuple)
        ):
            raise InvalidValueError("Workshop participants must be a list.")
        self._participants: list[str] = []
        for participant in participants:
            self._add_initial_participant(participant)
        if len(self._participants) > self.capacity:
            raise InvalidValueError(
                "A workshop cannot start with more participants than places."
            )

    @property
    def capacity(self) -> int:
        return min(self.max_participants, self.venue.capacity)

    @property
    def participants(self) -> tuple[str, ...]:
        return tuple(self._participants)

    @property
    def places_left(self) -> int:
        return self.capacity - len(self._participants)

    def _add_initial_participant(self, participant: str) -> None:
        name = clean_name(participant, "Participant name")
        if any(
            existing.casefold() == name.casefold() for existing in self._participants
        ):
            raise InvalidValueError(f"Participant '{name}' is registered twice.")
        self._participants.append(name)

    def register(self, participant: str) -> None:
        """Register one participant or raise a clear conflict."""
        name = clean_name(participant, "Participant name")
        if any(
            existing.casefold() == name.casefold() for existing in self._participants
        ):
            raise ConflictError(f"{name} is already registered for {self.title}.")
        if self.places_left < 1:
            raise ConflictError(f"{self.title} is full.")
        self._participants.append(name)

    def artist_slugs(self) -> tuple[str, ...]:
        return (self.teacher,)

    def role_for(self, artist_slug: str) -> str | None:
        return "teacher" if artist_slug == self.teacher else None

    def summary(self, artists: Mapping[str, Artist]) -> str:
        return (
            f"with {artists[self.teacher].name}, "
            f"{len(self._participants)}/{self.max_participants} places taken"
        )

    def specific_view(self, artists: Mapping[str, Artist]) -> dict[str, Any]:
        return {
            "teacher": self.teacher,
            "max_participants": self.max_participants,
            "participants": list(self._participants),
            "places_left": self.places_left,
        }

    def specific_record(self) -> dict[str, Any]:
        return {
            "teacher": self.teacher,
            "max_participants": self.max_participants,
            "participants": list(self._participants),
        }


def build_performance(data: Mapping[str, Any], venue: Venue) -> Performance:
    """Build the correct performance subclass from saved or request data."""
    if not isinstance(data, Mapping):
        raise InvalidValueError("A performance must be an object.")
    kind = data.get("kind")
    common = {
        "title": data.get("title"),
        "venue": venue,
        "start": data.get("start"),
        "duration_minutes": data.get("duration_minutes"),
        "description": data.get("description", ""),
    }
    if kind == "solo":
        if data.get("artist") is None or data.get("min_age") is None:
            raise InvalidValueError("A solo show needs an artist and a minimum age.")
        return SoloShow(
            **common,
            artist=data["artist"],
            min_age=data["min_age"],
        )
    if kind == "lineup":
        if data.get("host") is None or data.get("acts") is None:
            raise InvalidValueError("A lineup needs a host and acts.")
        return Lineup(
            **common,
            host=data["host"],
            acts=data["acts"],
        )
    if kind == "workshop":
        if data.get("teacher") is None or data.get("max_participants") is None:
            raise InvalidValueError(
                "A workshop needs a teacher and a maximum number of participants."
            )
        return Workshop(
            **common,
            teacher=data["teacher"],
            max_participants=data["max_participants"],
            participants=data.get("participants"),
        )
    raise InvalidValueError("Kind must be 'solo', 'lineup' or 'workshop'.")
