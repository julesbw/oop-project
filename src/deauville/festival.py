"""The festival aggregate and all cross-object business rules."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any

from .errors import ConflictError, InvalidValueError, NotFoundError
from .models import Artist, Performance, Venue, Workshop, build_performance
from .utils import clean_name, parse_local_datetime, slugify


class Festival:
    """Own every venue, artist and performance and enforce their invariants."""

    def __init__(
        self,
        name: str,
        first_day: date,
        last_day: date,
        venues: list[Venue],
        artists: list[Artist],
    ) -> None:
        self.name = clean_name(name, "Festival name")
        if first_day > last_day:
            raise InvalidValueError("The first festival day must come before the last.")
        self.first_day = first_day
        self.last_day = last_day
        self._venues: dict[str, Venue] = {}
        for venue in venues:
            if venue.slug in self._venues:
                raise ConflictError(f"Venue '{venue.slug}' already exists.")
            self._venues[venue.slug] = venue
        self._artists: dict[str, Artist] = {}
        for artist in artists:
            if artist.slug in self._artists:
                raise ConflictError(f"Artist '{artist.slug}' already exists.")
            self._artists[artist.slug] = artist
        self._performances: list[Performance] = []

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> Festival:
        """Build a validated festival from the JSON document."""
        if not isinstance(data, Mapping):
            raise InvalidValueError("The festival file must contain an object.")
        try:
            first_day = date.fromisoformat(data["first_day"])
            last_day = date.fromisoformat(data["last_day"])
            venues = [
                Venue(item["name"], item["capacity"], item["address"])
                for item in data["venues"]
            ]
            artists = [
                Artist(item["name"], item.get("bio", ""), item.get("photo_url", ""))
                for item in data["artists"]
            ]
            festival = cls(data["name"], first_day, last_day, venues, artists)
            for record in data["performances"]:
                venue = festival.get_venue(record["venue"])
                festival.add_performance_record(record, venue)
            return festival
        except KeyError as error:
            raise InvalidValueError(
                f"The festival file is missing '{error.args[0]}'."
            ) from error
        except (TypeError, ValueError) as error:
            raise InvalidValueError(
                f"The festival file is invalid: {error}."
            ) from error

    @property
    def venues(self) -> tuple[Venue, ...]:
        """Return venues in their insertion order."""
        return tuple(self._venues.values())

    @property
    def artists(self) -> tuple[Artist, ...]:
        """Return artists in alphabetical slug order."""
        return tuple(sorted(self._artists.values(), key=lambda artist: artist.slug))

    @property
    def performances(self) -> tuple[Performance, ...]:
        """Return performances in programme order."""
        return tuple(sorted(self._performances))

    @property
    def days(self) -> tuple[date, ...]:
        """Return every festival day, including days without performances."""
        count = (self.last_day - self.first_day).days + 1
        return tuple(self.first_day + timedelta(days=index) for index in range(count))

    def get_venue(self, slug: str) -> Venue:
        """Return a venue or raise a user-facing not-found error."""
        key = slugify(slug, "Venue")
        try:
            return self._venues[key]
        except KeyError as error:
            raise NotFoundError(f"No venue '{slug}'.") from error

    def get_artist(self, slug: str) -> Artist:
        """Return an artist or raise a user-facing not-found error."""
        key = slugify(slug, "Artist")
        try:
            return self._artists[key]
        except KeyError as error:
            raise NotFoundError(f"No artist '{slug}'.") from error

    def get_performance(self, performance_id: str) -> Performance:
        """Return a performance by its stable identifier."""
        for performance in self._performances:
            if performance.id == performance_id:
                return performance
        raise NotFoundError(f"No performance '{performance_id}'.")

    def add_artist(self, name: str, bio: str = "", photo_url: str = "") -> Artist:
        """Add an artist if its slug is not already used."""
        artist = Artist(name, bio, photo_url)
        if artist.slug in self._artists:
            raise ConflictError(f"Artist '{artist.slug}' already exists.")
        self._artists[artist.slug] = artist
        return artist

    def _build_performance(self, data: Mapping[str, Any]) -> Performance:
        venue_value = data.get("venue")
        if not isinstance(venue_value, str) or not venue_value.strip():
            raise InvalidValueError("A performance needs a venue.")
        venue = self.get_venue(venue_value)
        return build_performance(data, venue)

    def add_performance_record(
        self, data: Mapping[str, Any], venue: Venue | None = None
    ) -> Performance:
        """Build, validate and append a performance record."""
        if venue is None:
            venue = self.get_venue(data["venue"])
        performance = build_performance(data, venue)
        self._validate_performance(performance)
        self._performances.append(performance)
        return performance

    def add_performance(self, data: Mapping[str, Any]) -> Performance:
        """Build, validate and append a performance from a request."""
        return self.add_performance_record(data, self.get_venue(data["venue"]))

    def _validate_performance(
        self, candidate: Performance, ignore_id: str | None = None
    ) -> None:
        for artist_slug in candidate.artist_slugs():
            if artist_slug not in self._artists:
                raise NotFoundError(f"No artist '{artist_slug}'.")

        if not self.first_day <= candidate.festival_day <= self.last_day:
            raise ConflictError(
                f"{candidate.festival_day.isoformat()} is not a day of the festival."
            )

        for other in self._performances:
            if other.id == ignore_id:
                continue
            if other.id == candidate.id:
                raise ConflictError(f"Performance '{candidate.id}' already exists.")
            if not self._too_close(candidate, other):
                continue
            if candidate.venue.slug == other.venue.slug:
                raise ConflictError(
                    f"{candidate.venue.name} is busy with {other.title} "
                    f"({other.start:%Y-%m-%d %H:%M}-{other.end:%H:%M}). "
                    "Leave 30 minutes between two shows."
                )
            common_artists = set(candidate.artist_slugs()) & set(other.artist_slugs())
            if common_artists:
                artist = self._artists[next(iter(common_artists))]
                raise ConflictError(
                    f"{artist.name} is on stage in {other.title} "
                    f"({other.start:%Y-%m-%d %H:%M}-{other.end:%H:%M}). "
                    "Leave 30 minutes between two performances."
                )

    @staticmethod
    def _too_close(first: Performance, second: Performance) -> bool:
        gap = timedelta(minutes=30)
        return first.start < second.end + gap and second.start < first.end + gap

    def replace_performance(
        self, performance_id: str, data: Mapping[str, Any]
    ) -> Performance:
        """Replace a performance transactionally at the aggregate level."""
        old = self.get_performance(performance_id)
        if (
            isinstance(old, Workshop)
            and data.get("kind") == "workshop"
            and "participants" not in data
        ):
            data = {**data, "participants": list(old.participants)}
        candidate = self._build_performance(data)
        self._validate_performance(candidate, ignore_id=old.id)
        index = self._performances.index(old)
        self._performances[index] = candidate
        return candidate

    def remove_performance(self, performance_id: str) -> Performance:
        """Remove and return a performance."""
        performance = self.get_performance(performance_id)
        self._performances.remove(performance)
        return performance

    def programme(
        self, day: date | None = None, venue: str | None = None
    ) -> list[Performance]:
        """Return performances filtered and ordered for the programme."""
        venue_slug = None
        if venue is not None:
            venue_slug = self.get_venue(venue).slug
        return [
            performance
            for performance in self.performances
            if (day is None or performance.festival_day == day)
            and (venue_slug is None or performance.venue.slug == venue_slug)
        ]

    def performances_for_artist(self, artist_slug: str) -> list[Performance]:
        """Return every performance involving an artist."""
        artist = self.get_artist(artist_slug)
        return [
            performance
            for performance in self.performances
            if artist.slug in performance.artist_slugs()
        ]

    def now(self, at: datetime) -> tuple[list[Performance], list[Performance]]:
        """Return shows running at a moment and the next three shows."""
        moment = parse_local_datetime(at, "Moment")
        current = [
            performance
            for performance in self.performances
            if performance.start <= moment < performance.end
        ]
        upcoming = [
            performance
            for performance in self.performances
            if performance.start > moment
        ][:3]
        return current, upcoming

    def register_participant(self, performance_id: str, name: str) -> Workshop:
        """Register a participant on a workshop."""
        performance = self.get_performance(performance_id)
        if not isinstance(performance, Workshop):
            raise InvalidValueError("Participants can only register for workshops.")
        performance.register(name)
        return performance

    def to_view(self) -> dict[str, Any]:
        """Return the festival metadata used by the API."""
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "days": [day.isoformat() for day in self.days],
        }

    def to_data(self) -> dict[str, Any]:
        """Return the complete validated document for JSON storage."""
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "venues": [venue.to_record() for venue in self.venues],
            "artists": [artist.to_record() for artist in self.artists],
            "performances": [
                performance.to_record() for performance in self.performances
            ],
        }
