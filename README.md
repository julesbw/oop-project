# Deauville Festival du Rire

Deauville Festival du Rire is a complete Python platform for the 10–13 June
2027 programme. It provides a command line, a FastAPI web application, a public
programme website and an administration interface for organisers.

The project follows the B1–B5 track. This README documents the finished
implementation, its architecture and how to run it.

## What you get

| Path                                     | Content                                                        |
| ---------------------------------------- | -------------------------------------------------------------- |
| [data/festival.json](data/festival.json) | the 2027 edition: 4 venues, 12 artists, 23 performances        |
| [web/public/](web/public/)               | the public website: programme, artists, "now on stage"         |
| [web/admin/](web/admin/)                 | the admin: schedule, move and cancel performances, add artists |
| [API.md](API.md)                         | the HTTP contract the website and the admin rely on            |
| [main.py](main.py)                       | compatibility entry point for the packaged CLI                 |

The two HTML folders are static clients. They communicate with the packaged
FastAPI application through the routes defined in `API.md`.

## Implemented features

1. **Festival domain model**: venues, artists and three kinds of performances.
   All scheduling rules are enforced by the domain, regardless of the caller.
2. **JSON storage**: the festival is loaded from `data/festival.json` and
   saved after every successful change.
3. **Command line**: programme, venue, artist, current/upcoming performances,
   adding and cancelling shows, plus the server command.
4. **FastAPI application**: the complete `API.md` contract under `/api`, the
   public website at `/` and the admin interface at `/admin/`.
5. **Automated tests**: pytest tests for domain rules, persistence and HTTP
   behaviour.

## Domain rules

### Names and identifiers

- Every name (artist, venue, performance title, participant) is stored without
  the spaces around it, and cannot be empty.
- Artists and venues are identified by a **slug**: lower case ASCII letters,
  digits and single dashes, accents removed.
  `"Théâtre des Planches"` → `"theatre-des-planches"`,
  `"Élodie  Marchal !"` → `"elodie-marchal"`. Two artists with the same slug
  are the same artist; same for venues.
- A performance is identified by its venue slug and its start:
  `"le-kiosque-2027-06-12-0100"`.
- Artists are listed in alphabetical order of their slug (`Élodie` before
  `Hugo`); venues in the order they were added; performances by start time,
  then by venue name.

### Venues, performances and time

- A venue has a name, a number of seats (at least 1) and an address.
- Every performance has a title, a venue, a start (local time, no time zone),
  a duration from 1 to 360 minutes, and a description that may be empty.
- **A festival day ends at 06:00.** A show starting at 00:30 on 12 June is
  part of the 11 June programme.
- A performance must belong to a day of the festival (`first_day` to
  `last_day` of the data file).
- A venue needs **30 minutes** between the end of a performance and the start
  of the next one.
- An artist needs **30 minutes** between two performances, in any venue and
  in any role (solo artist, host, act, teacher).
- Venue, artists and performances referenced by slug or id must exist.

### Three kinds of performances

| Kind       | Who is on stage                     | Specific rules                                                                                                                 |
| ---------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `solo`     | one artist                          | a minimum age for the audience, from 0 (everyone) to 18                                                                        |
| `lineup`   | a host, then acts one after another | at least 2 acts, each one only once; the host is not an act; each act needs 10 minutes and the host 3 minutes between two acts |
| `workshop` | a teacher, plus participants        | `max_participants` at least 1; registration by name, until full                                                                |

- A lineup of 3 acts lasts at least `3 × 10 + 2 × 3 = 36` minutes.
- A workshop has `min(max_participants, venue seats)` places. Participant
  names are compared without case: `"Camille R."` is already registered if
  `"camille r."` is.
- The capacity of a solo show or a lineup is the number of seats of its venue.

### Errors

Every broken rule gives a sentence a festival organiser understands:
`"Le Kiosque is busy with After Hours (2027-06-12 01:00-02:00). Leave 30
minutes between two shows."`, not `KeyError: 'le-kiosque'`. The web API
turns these errors into the status codes listed in `API.md` (404, 409, 422,
500).

A change that breaks a rule changes nothing: moving a performance onto a busy
slot leaves it where it was.

## Architecture decisions

`Festival` is the aggregate root: callers access performances through it, so
venue, artist, date, lineup and workshop rules cannot be bypassed. The
abstract `Performance` class contains shared scheduling behaviour, while
`SoloShow`, `Lineup` and `Workshop` implement their own participants,
validation and API views.

Domain errors are represented by a small exception hierarchy. The CLI renders
them as readable messages and FastAPI maps them to the status codes from
`API.md`. Storage is isolated behind the `Storage` interface, so replacing the
JSON file with another backend would not require changing the domain classes.

## Getting started

From a fresh clone, install the environment and run the compatibility entry
point:

```bash
uv sync
uv run main.py
```

## Status

The B1–B5 track is complete. The CLI, web application, admin workflows,
storage abstraction, domain rules, tests and packaging are implemented.
The seed data in `data/festival.json` remains unchanged by the test suite.

### Install and run

~~~bash
uv sync
uv run main.py
uv run deauville programme 2027-06-11
uv run deauville artist max-pellerin
uv run deauville now 2027-06-11T21:00
uv run deauville serve
~~~

The website is available at `http://127.0.0.1:8000/`, the admin at
`http://127.0.0.1:8000/admin/`, and the API documentation at
`http://127.0.0.1:8000/docs`.

Run the checks with:

~~~bash
uv run pytest
uv run ruff check src tests main.py
uv build
~~~

### Structure

- `src/deauville/models.py` contains `Venue`, `Artist`, the abstract
  `Performance`, and `SoloShow`, `Lineup` and `Workshop`.
- `src/deauville/festival.py` is the aggregate root. All scheduling,
  artist, date, lineup and workshop rules go through it.
- `src/deauville/storage.py` separates JSON persistence from the domain and
  provides an in-memory storage for tests.
- `src/deauville/cli.py` implements the CLI commands and `serve`.
- `src/deauville/api.py` implements the contract in `API.md`, maps domain
  errors to HTTP statuses, and mounts both websites.
- `tests/` verifies the domain rules, date boundary, persistence behaviour
  and HTTP contract.

The model does not know where the data is stored. Replacing JSON with another
storage would only require another "Storage" implementation and wiring it into
the CLI or application factory.

The 06:00 festival-day rule is implemented with real datetime values:
`2027-06-12T01:00` belongs to the `2027-06-11` programme.
