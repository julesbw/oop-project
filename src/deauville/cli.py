"""Command line interface for the festival."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from .errors import FestivalError, InvalidValueError, StorageError
from .festival import Festival
from .models import Performance
from .storage import JsonStorage, Storage

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def default_data_path() -> Path:
    """Find the data file when called from the project or another directory."""
    local_path = Path("data/festival.json")
    return local_path if local_path.exists() else PROJECT_ROOT / "data/festival.json"


def _short_day(day: date) -> str:
    return f"{day:%a} {day.day:02d}"


def _long_day(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B}"


def _range(performance: Performance) -> str:
    return f"{performance.start:%H:%M}-{performance.end:%H:%M}"


def print_summary(festival: Festival) -> None:
    """Print the B1 summary."""
    print(festival.name)
    print(f"From {festival.first_day} to {festival.last_day}")
    print(
        f"{len(festival.venues)} venues, "
        f"{len(festival.artists)} artists, "
        f"{len(festival.performances)} performances"
    )


def print_exploration(festival: Festival) -> None:
    """Print the exploratory B1 report."""
    print_summary(festival)
    print("\nVenues:")
    total = 0
    for venue in festival.venues:
        total += venue.capacity
        print(f"- {venue.name}: {venue.capacity} seats ({venue.address})")
    print(f"Total: {total} seats\n")

    counts: dict[str, int] = {}
    for performance in festival.performances:
        counts[performance.kind] = counts.get(performance.kind, 0) + 1
    for kind in ("lineup", "solo", "workshop"):
        if kind in counts:
            print(f"{kind}: {counts[kind]}")
    print("\nAt Le Kiosque:")
    for performance in festival.programme(venue="le-kiosque"):
        print(
            f"- {performance.start.isoformat(timespec='minutes')} {performance.title}"
        )
    longest = max(festival.performances, key=lambda item: item.duration_minutes)
    print(f"\nLongest: {longest.title} ({longest.duration_minutes} min)\n")
    artists = {artist.slug: artist for artist in festival.artists}
    for performance in festival.performances:
        if performance.kind == "workshop":
            view = performance.to_view(artists)
            print(
                f"{performance.title} on {performance.festival_day}: "
                f"{len(view['participants'])}/{view['max_participants']} registered"
            )
    print()

    counts_by_artist: dict[str, int] = {}
    for performance in festival.performances:
        for artist_slug in performance.artist_slugs():
            counts_by_artist[artist_slug] = counts_by_artist.get(artist_slug, 0) + 1
    maximum = max(counts_by_artist.values(), default=0)
    leaders = [slug for slug, count in counts_by_artist.items() if count == maximum]
    print(f"On stage {maximum} times: {', '.join(leaders)}")


def print_venues(festival: Festival) -> None:
    """Print venues in insertion order."""
    total = 0
    for venue in festival.venues:
        print(f"{venue.slug}: {venue.name}, {venue.capacity} seats")
        total += venue.capacity
    print(f"Total: {total} seats")


def print_programme(festival: Festival, day: date) -> None:
    """Print one festival day with computed end times."""
    print(f"Programme for {_long_day(day)}:")
    for performance in festival.programme(day=day):
        print(
            f"{_range(performance)} | {performance.venue.name} | "
            f"{performance.title} ({performance.kind})"
        )


def print_artist(festival: Festival, slug: str) -> None:
    """Print every performance and role for one artist."""
    artist = festival.get_artist(slug)
    print(artist.name)
    for performance in festival.performances_for_artist(artist.slug):
        role = performance.role_for(artist.slug)
        print(
            f"{_short_day(performance.festival_day)} "
            f"{_range(performance)} | {performance.venue.name} | "
            f"{performance.title} ({role})"
        )


def print_now(festival: Festival, moment: datetime) -> None:
    """Print current and upcoming performances."""
    current, upcoming = festival.now(moment)
    print(f"On stage at {moment:%Y-%m-%d %H:%M}:")
    for performance in current:
        print(
            f"- {performance.title} at {performance.venue.name}, "
            f"until {performance.end:%H:%M}"
        )
    if not current:
        print("- Nothing is on stage.")
    print("Up next:")
    for performance in upcoming:
        print(
            f"- {_range(performance)} | {performance.venue.name} | "
            f"{performance.title} ({performance.kind})"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deauville Festival du Rire programme")
    parser.add_argument("--data", type=Path, default=None, help="JSON data file")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("explore", help="print the B1 data exploration")
    commands.add_parser("venues", help="list venues")
    programme = commands.add_parser("programme", help="print a festival day")
    programme.add_argument("day", nargs="?", help="YYYY-MM-DD")
    artist = commands.add_parser("artist", help="print an artist's programme")
    artist.add_argument("slug")
    now = commands.add_parser("now", help="show current and next performances")
    now.add_argument("moment", help="YYYY-MM-DDTHH:MM")
    commands.add_parser("add", help="add a solo performance interactively")
    cancel = commands.add_parser("cancel", help="cancel a performance")
    cancel.add_argument("performance_id")
    serve = commands.add_parser("serve", help="serve the website and API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    return parser


def _add_interactively(festival: Festival) -> Performance:
    title = input("Title: ")
    artist = input("Artist (slug): ")
    venue = input("Venue (slug): ")
    start = input("Start (YYYY-MM-DDTHH:MM): ")
    duration_text = input("Duration (minutes): ")
    try:
        duration = int(duration_text)
    except ValueError as error:
        raise InvalidValueError(
            f"{duration_text!r} is not a number of minutes."
        ) from error
    return festival.add_performance(
        {
            "kind": "solo",
            "title": title,
            "artist": artist,
            "venue": venue,
            "start": start,
            "duration_minutes": duration,
            "min_age": 0,
            "description": "",
        }
    )


def _run_command(args: argparse.Namespace, storage: Storage) -> None:
    festival = storage.load()
    if args.command is None:
        print_summary(festival)
    elif args.command == "explore":
        print_exploration(festival)
    elif args.command == "venues":
        print_venues(festival)
    elif args.command == "programme":
        day_text = args.day or input("Day (YYYY-MM-DD): ").strip()
        try:
            day = date.fromisoformat(day_text)
        except ValueError as error:
            raise InvalidValueError(
                f"{day_text!r} is not a day, use YYYY-MM-DD."
            ) from error
        print_programme(festival, day)
    elif args.command == "artist":
        print_artist(festival, args.slug)
    elif args.command == "now":
        try:
            moment = datetime.fromisoformat(args.moment)
        except ValueError as error:
            raise InvalidValueError(
                f"{args.moment!r} is not a valid moment, use YYYY-MM-DDTHH:MM."
            ) from error
        print_now(festival, moment)
    elif args.command == "add":
        performance = _add_interactively(festival)
        storage.save(festival)
        print(f"Added: {performance.id}")
    elif args.command == "cancel":
        performance = festival.remove_performance(args.performance_id)
        storage.save(festival)
        print(f"Cancelled: {performance.title}")
    elif args.command == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(storage), host=args.host, port=args.port)


def main(
    argv: Sequence[str] | None = None,
    storage: Storage | None = None,
) -> int:
    """Run the CLI and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if storage is None:
        data_path = args.data or default_data_path()
        storage = JsonStorage(data_path)
    try:
        _run_command(args, storage)
    except (FestivalError, StorageError) as error:
        print(f"Error: {error}")
        return 1
    return 0
