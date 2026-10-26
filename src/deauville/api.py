"""FastAPI application for the public website and admin."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .errors import FestivalError, StorageError
from .festival import Festival
from .storage import JsonStorage, Storage

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "festival.json"
DEFAULT_PUBLIC_DIR = PROJECT_ROOT / "web" / "public"
DEFAULT_ADMIN_DIR = PROJECT_ROOT / "web" / "admin"


class StrictBody(BaseModel):
    """Base model that rejects fields outside the HTTP contract."""

    model_config = ConfigDict(extra="forbid")


class ArtistBody(StrictBody):
    """JSON body used to create an artist."""

    name: str
    bio: str = ""
    photo_url: str = ""


class CommonPerformanceBody(StrictBody):
    """Fields shared by every performance request."""

    title: str
    venue: str
    start: datetime
    duration_minutes: int = Field(ge=1, le=360)
    description: str = ""


class SoloPerformanceBody(CommonPerformanceBody):
    """JSON body for a solo show."""

    kind: Literal["solo"]
    artist: str
    min_age: int = Field(ge=0, le=18)


class LineupPerformanceBody(CommonPerformanceBody):
    """JSON body for a lineup."""

    kind: Literal["lineup"]
    host: str
    acts: list[str]


class WorkshopPerformanceBody(CommonPerformanceBody):
    """JSON body for a workshop."""

    kind: Literal["workshop"]
    teacher: str
    max_participants: int = Field(ge=1)
    participants: list[str] | None = None


PerformanceBody = Annotated[
    SoloPerformanceBody | LineupPerformanceBody | WorkshopPerformanceBody,
    Field(discriminator="kind"),
]


class ParticipantBody(StrictBody):
    """JSON body used to register a workshop participant."""

    name: str


def _model_dump(model: BaseModel) -> dict[str, Any]:
    """Support the installed Pydantic serialisation API."""
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


class FestivalState:
    """Lazy, transactional access to one storage implementation."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self._festival: Festival | None = None

    def get(self) -> Festival:
        """Load the festival once and surface storage failures to the API."""
        if self._festival is None:
            self._festival = self.storage.load()
        return self._festival

    def write(self, operation: Callable[[Festival], Any]) -> Any:
        """Apply a validated operation and save it, restoring on write failure."""
        festival = self.get()
        snapshot = festival.to_data()
        try:
            result = operation(festival)
            self.storage.save(festival)
            return result
        except StorageError:
            self._festival = Festival.from_data(snapshot)
            raise


def create_app(
    storage: Storage,
    public_dir: Path = DEFAULT_PUBLIC_DIR,
    admin_dir: Path = DEFAULT_ADMIN_DIR,
) -> FastAPI:
    """Create an application around an injected storage."""
    app = FastAPI(title="Deauville Festival du Rire")
    state = FestivalState(storage)
    app.state.festival_state = state

    @app.exception_handler(FestivalError)
    async def festival_error_handler(
        request: Request, error: FestivalError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": str(error)},
        )

    @app.exception_handler(StorageError)
    async def storage_error_handler(
        request: Request, error: StorageError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": str(error)},
        )

    @app.get("/api/festival")
    def get_festival() -> dict[str, Any]:
        return state.get().to_view()

    @app.get("/api/venues")
    def list_venues() -> list[dict[str, Any]]:
        return [venue.to_view() for venue in state.get().venues]

    @app.get("/api/artists")
    def list_artists() -> list[dict[str, Any]]:
        return [artist.to_view() for artist in state.get().artists]

    @app.get("/api/artists/{slug}")
    def get_artist(slug: str) -> dict[str, Any]:
        festival = state.get()
        artist = festival.get_artist(slug)
        result = artist.to_view()
        result["performances"] = [
            performance.to_view({item.slug: item for item in festival.artists})
            for performance in festival.performances_for_artist(artist.slug)
        ]
        return result

    @app.get("/api/programme")
    def get_programme(
        day: date | None = None,
        venue: str | None = None,
    ) -> list[dict[str, Any]]:
        festival = state.get()
        artists = {artist.slug: artist for artist in festival.artists}
        return [
            performance.to_view(artists)
            for performance in festival.programme(day=day, venue=venue)
        ]

    @app.get("/api/performances/{performance_id}")
    def get_performance(performance_id: str) -> dict[str, Any]:
        festival = state.get()
        performance = festival.get_performance(performance_id)
        artists = {artist.slug: artist for artist in festival.artists}
        return performance.to_view(artists)

    @app.get("/api/now")
    def get_now(at: datetime | None = None) -> dict[str, Any]:
        festival = state.get()
        moment = at or datetime.now()
        current, upcoming = festival.now(moment)
        artists = {artist.slug: artist for artist in festival.artists}
        return {
            "at": moment.isoformat(timespec="minutes"),
            "now_playing": [performance.to_view(artists) for performance in current],
            "up_next": [performance.to_view(artists) for performance in upcoming],
        }

    @app.post("/api/artists", status_code=201)
    def create_artist(body: ArtistBody) -> dict[str, Any]:
        artist = state.write(
            lambda festival: festival.add_artist(
                body.name,
                body.bio,
                body.photo_url,
            )
        )
        return artist.to_view()

    @app.post("/api/performances", status_code=201)
    def create_performance(body: PerformanceBody) -> dict[str, Any]:
        performance = state.write(
            lambda festival: festival.add_performance(_model_dump(body))
        )
        artists = {artist.slug: artist for artist in state.get().artists}
        return performance.to_view(artists)

    @app.put("/api/performances/{performance_id}")
    def update_performance(
        performance_id: str, body: PerformanceBody
    ) -> dict[str, Any]:
        performance = state.write(
            lambda festival: festival.replace_performance(
                performance_id,
                _model_dump(body),
            )
        )
        artists = {artist.slug: artist for artist in state.get().artists}
        return performance.to_view(artists)

    @app.delete("/api/performances/{performance_id}", status_code=204)
    def delete_performance(performance_id: str) -> Response:
        state.write(lambda festival: festival.remove_performance(performance_id))
        return Response(status_code=204)

    @app.post("/api/performances/{performance_id}/participants", status_code=201)
    def register_participant(
        performance_id: str, body: ParticipantBody
    ) -> dict[str, Any]:
        performance = state.write(
            lambda festival: festival.register_participant(performance_id, body.name)
        )
        artists = {artist.slug: artist for artist in state.get().artists}
        return performance.to_view(artists)

    app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin")
    app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")
    return app


app = create_app(JsonStorage(DEFAULT_DATA_PATH))
