# Deauville Festival du Rire - project brief

The Deauville Festival du Rire (10-13 June 2027) needs a platform for its
programme: artists, venues and shows, with the scheduling rules a generic CMS
cannot enforce. The website and the admin are already written. Everything
behind them is yours to build, in Python.

> The original brief is retained below as the project specification. The
> implementation and run instructions are documented in [Implementation](#implementation).

## What you get

| Path                                     | Content                                                        |
| ---------------------------------------- | -------------------------------------------------------------- |
| [data/festival.json](data/festival.json) | the 2027 edition: 4 venues, 12 artists, 23 performances        |
| [web/public/](web/public/)               | the public website: programme, artists, "now on stage"         |
| [web/admin/](web/admin/)                 | the admin: schedule, move and cancel performances, add artists |
| [API.md](API.md)                         | the HTTP contract the website and the admin rely on            |
| [main.py](main.py)                       | compatibility entry point for the packaged CLI                 |

That is all: no package, no class, no test. The structure of the project is
part of the work. The two HTML folders are static files; they only talk to
your server through the routes of `API.md`.

## What you build

1. **The festival model**: venues, artists, three kinds of performances, and
   the rules below. A rule must hold whoever uses the model: the command line,
   the web API, or a test.
2. **Storage**: load the festival from `data/festival.json`, save it back
   after every change. Loading checks every rule again: a broken file gives a
   clear error, not a traceback.
3. **A command line**, at least:
   - the programme of one festival day, in order;
   - the list of the artists with their number of shows;
   - what is on stage at a given moment, and the next 3 performances.
4. **A web server**, with FastAPI: the routes of [API.md](API.md) under
   `/api`, `web/public/` served at `/` and `web/admin/` at `/admin/`.
5. **Your tests** (pytest), written along the way.

## The rules

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

## Your decisions

Nobody will tell you which modules or classes to write. Decide, then explain
your choices in your README. A few questions to answer before coding:

- Which objects does the festival have? What does each one know, what does
  each one check?
- What do the three kinds of performances share, and what differs?
- Where does a rule live so that neither the command line nor the API can
  bypass it? Can a caller add a performance without going through it?
- How does the code calling the model know _which_ rule was broken?
- If the data moved from a JSON file to a database tomorrow, which files
  would change?

You will defend these choices at the oral, on your own code.

## Start

The project has completed the B1-B5 track. From a fresh clone, install the
environment and run the compatibility entry point:

```bash
uv sync
uv run main.py
```

## Levels

| Level | Status   | Criteria                                                                                                         |
| ----- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| P1    | required | the program runs from a fresh clone, the rules hold, errors give clear messages, the code reads well             |
| P2    | expected | coherent classes: inheritance and abstract classes where they fit, encapsulation, your own errors, storage apart |
| P3    | bonus    | `ruff format` and `ruff check` clean, type annotations, docstrings, your tests, `uv build` works, the web API    |

Extension: a second storage in a SQLite database (e.g. SQLModel), usable in
place of the JSON file without changing the model.

## Submission

The last push before the deadline is graded. Your README replaces this one
and says:

- what the project does, how to install it, run it and run the tests;
- your structure: the modules and classes, and why (the questions above);
- what is done, and what is not.

A fresh clone must work with `uv sync`, then the commands of your README.

## Implementation

This repository follows the B1-B5 project track and now contains the complete
CLI, domain model, JSON storage, FastAPI application and test suite.

### Install and run

~~~bash
uv sync
uv run main.py
uv run deauville programme 2027-06-11
uv run deauville artist max-pellerin
uv run deauville now 2027-06-11T21:00
uv run deauville serve
~~~

The website is available at "http://127.0.0.1:8000/", the admin at
"http://127.0.0.1:8000/admin/", and the API documentation at
"http://127.0.0.1:8000/docs".

Run the checks with:

~~~bash
uv run pytest
uv run ruff check src tests main.py
uv build
~~~

### Structure

- "src/deauville/models.py" contains "Venue", "Artist", the abstract
  "Performance", and "SoloShow", "Lineup" and "Workshop".
- "src/deauville/festival.py" is the aggregate root. All scheduling,
  artist, date, lineup and workshop rules go through it.
- "src/deauville/storage.py" separates JSON persistence from the domain and
  provides an in-memory storage for tests.
- "src/deauville/cli.py" implements the B1/B2 commands and "serve".
- "src/deauville/api.py" implements the contract in "API.md", maps domain
  errors to HTTP statuses, and mounts both websites.
- "tests/" verifies the domain rules, date boundary, persistence behaviour
  and HTTP contract.

The model does not know where the data is stored. Replacing JSON with another
storage would only require another "Storage" implementation and wiring it into
the CLI or application factory.

The 06:00 festival-day rule is implemented with real datetime values:
"2027-06-12T01:00" belongs to the "2027-06-11" programme.
