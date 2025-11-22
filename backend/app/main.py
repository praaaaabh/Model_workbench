from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STANDARD_VARIABLES = {
    "age",
    "sex",
    "height",
    "weight",
    "bp_systolic",
    "bp_diastolic",
    "cholesterol",
    "glucose",
    "patient_id",
    "visit_date",
}


class ColumnSchema(BaseModel):
    name: str
    inferred_type: str


class DatasetRecord(BaseModel):
    id: str
    filename: str
    stored_path: Path
    columns: list[ColumnSchema]
    mapping: dict[str, str]
    suggestions: dict[str, str]


class DatasetResponse(BaseModel):
    id: str
    filename: str
    columns: list[ColumnSchema]
    mapping: dict[str, str]
    suggestions: dict[str, str]


class UpdateMappingRequest(BaseModel):
    mapping: dict[str, str]


class DatasetStore:
    def __init__(self) -> None:
        self._records: dict[str, DatasetRecord] = {}

    def add(self, record: DatasetRecord) -> None:
        self._records[record.id] = record

    def get(self, dataset_id: str) -> DatasetRecord:
        if dataset_id not in self._records:
            raise KeyError(dataset_id)
        return self._records[dataset_id]

    def update_mapping(self, dataset_id: str, mapping: dict[str, str]) -> DatasetRecord:
        record = self.get(dataset_id)
        record.mapping = mapping
        self._records[dataset_id] = record
        return record

    def clear(self) -> None:
        self._records = {}


dataset_store = DatasetStore()


class ProfileStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ColumnProfile(BaseModel):
    name: str
    inferred_type: str
    non_nulls: int
    missing: int
    sample_values: list[str]


class DatasetProfileResponse(BaseModel):
    status: ProfileStatus
    row_count: int | None = None
    column_count: int | None = None
    columns: list[ColumnProfile] = Field(default_factory=list)
    artifact_url: str | None = None
    updated_at: datetime
    message: str | None = None


class CachedProfile(BaseModel):
    dataset_id: str
    status: ProfileStatus
    row_count: int | None = None
    column_count: int | None = None
    columns: list[ColumnProfile] = Field(default_factory=list)
    artifact_path: Path | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    message: str | None = None


class ProfileCache:
    """Simulates a Postgres cache table for dataset profiling."""

    def __init__(self) -> None:
        self._profiles: dict[str, CachedProfile] = {}

    def start(self, dataset_id: str) -> CachedProfile:
        existing = self._profiles.get(dataset_id)
        if existing and existing.artifact_path:
            existing.artifact_path.unlink(missing_ok=True)

        profile = CachedProfile(dataset_id=dataset_id, status=ProfileStatus.PENDING, columns=[])
        self._profiles[dataset_id] = profile
        return profile

    def complete(
        self,
        dataset_id: str,
        row_count: int,
        column_count: int,
        columns: list[ColumnProfile],
        artifact_path: Path,
    ) -> CachedProfile:
        profile = CachedProfile(
            dataset_id=dataset_id,
            status=ProfileStatus.COMPLETED,
            row_count=row_count,
            column_count=column_count,
            columns=columns,
            artifact_path=artifact_path,
            updated_at=datetime.utcnow(),
        )
        self._profiles[dataset_id] = profile
        return profile

    def fail(self, dataset_id: str, message: str) -> CachedProfile:
        profile = CachedProfile(
            dataset_id=dataset_id,
            status=ProfileStatus.FAILED,
            message=message,
            updated_at=datetime.utcnow(),
        )
        self._profiles[dataset_id] = profile
        return profile

    def get(self, dataset_id: str) -> CachedProfile:
        if dataset_id not in self._profiles:
            raise KeyError(dataset_id)
        return self._profiles[dataset_id]

    def clear(self) -> None:
        for profile in self._profiles.values():
            if profile.artifact_path:
                profile.artifact_path.unlink(missing_ok=True)
        self._profiles = {}


profile_cache = ProfileCache()


def _infer_value_type(value: str) -> str:
    if value == "":
        return "unknown"
    try:
        int(value)
        return "integer"
    except ValueError:
        try:
            float(value)
            return "float"
        except ValueError:
            return "string"


def infer_schema(file_path: Path) -> list[ColumnSchema]:
    with file_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError("Unable to read CSV header for schema inference")

        sample_types: dict[str, list[str]] = {name: [] for name in reader.fieldnames}

        for index, row in enumerate(reader):
            for key, value in row.items():
                sample_types[key].append(_infer_value_type(value or ""))
            if index >= 49:
                break

    columns: list[ColumnSchema] = []
    for name, values in sample_types.items():
        inferred = "string"
        non_unknown = [v for v in values if v != "unknown"]
        if non_unknown and all(v == "integer" for v in non_unknown):
            inferred = "integer"
        elif non_unknown and all(v in {"integer", "float"} for v in non_unknown):
            inferred = "float"

        columns.append(ColumnSchema(name=name, inferred_type=inferred))

    return columns


def _suggest_for_column(column_name: str) -> str | None:
    normalized = column_name.lower().replace(" ", "_")
    for variable in STANDARD_VARIABLES:
        if normalized == variable:
            return variable
        if variable in normalized:
            return variable
    return None


def build_suggestions(columns: list[ColumnSchema]) -> dict[str, str]:
    suggestions: dict[str, str] = {}
    for column in columns:
        suggestion = _suggest_for_column(column.name)
        if suggestion:
            suggestions[column.name] = suggestion
    return suggestions


def profile_dataset(record: DatasetRecord) -> tuple[int, int, list[ColumnProfile]]:
    """Compute lightweight profiling metrics for the uploaded CSV file."""

    row_count = 0
    column_profiles: dict[str, ColumnProfile] = {}

    with record.stored_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Unable to read CSV header for profiling")

        for name in reader.fieldnames:
            column_profiles[name] = ColumnProfile(
                name=name,
                inferred_type="unknown",
                non_nulls=0,
                missing=0,
                sample_values=[],
            )

        for row in reader:
            row_count += 1
            for name, value in row.items():
                column_profile = column_profiles[name]
                if value in {None, ""}:
                    column_profile.missing += 1
                else:
                    column_profile.non_nulls += 1
                    if len(column_profile.sample_values) < 3:
                        column_profile.sample_values.append(str(value))

    # Enrich inferred types using the schema inference for consistency
    inferred_columns = {column.name: column.inferred_type for column in record.columns}
    for column_name, profile in column_profiles.items():
        profile.inferred_type = inferred_columns.get(column_name, "unknown")

    column_count = len(column_profiles)
    return row_count, column_count, list(column_profiles.values())


def save_profile_artifact(dataset_id: str, profile: DatasetProfileResponse) -> Path:
    artifact_path = DATA_DIR / f"{dataset_id}_profile.json"
    with artifact_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "dataset_id": dataset_id,
                "status": profile.status.value,
                "row_count": profile.row_count,
                "column_count": profile.column_count,
                "columns": [column.model_dump() for column in profile.columns],
                "updated_at": profile.updated_at.isoformat(),
                "message": profile.message,
            },
            handle,
            indent=2,
        )
    return artifact_path


def build_profile_response(cache_entry: CachedProfile, app: FastAPI) -> DatasetProfileResponse:
    artifact_url = None
    try:
        artifact_url = app.url_path_for("download_profile_artifact", dataset_id=cache_entry.dataset_id)
    except Exception:
        artifact_url = None

    return DatasetProfileResponse(
        status=cache_entry.status,
        row_count=cache_entry.row_count,
        column_count=cache_entry.column_count,
        columns=cache_entry.columns,
        artifact_url=str(artifact_url) if artifact_url else None,
        updated_at=cache_entry.updated_at,
        message=cache_entry.message,
    )


def run_profile_job(dataset_id: str) -> None:
    try:
        record = dataset_store.get(dataset_id)
    except KeyError:
        profile_cache.fail(dataset_id, "Dataset not found")
        return

    try:
        row_count, column_count, columns = profile_dataset(record)
    except Exception as exc:  # pragma: no cover - defensive guard
        profile_cache.fail(dataset_id, str(exc))
        return

    completed = profile_cache.complete(
        dataset_id=dataset_id,
        row_count=row_count,
        column_count=column_count,
        columns=columns,
        artifact_path=DATA_DIR / f"{dataset_id}_profile.json",
    )
    artifact_profile = build_profile_response(completed, app)
    save_profile_artifact(dataset_id, artifact_profile)


def save_upload_file(upload_file: UploadFile, dataset_id: str) -> Path:
    stored_name = f"{dataset_id}_{upload_file.filename}"
    stored_path = DATA_DIR / stored_name
    with stored_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return stored_path


def get_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Model Workbench API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
    async def create_dataset(file: UploadFile = File(...)) -> DatasetResponse:
        dataset_id = str(uuid4())
        stored_path = save_upload_file(file, dataset_id)

        try:
            columns = infer_schema(stored_path)
        except ValueError as error:
            stored_path.unlink(missing_ok=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

        suggestions = build_suggestions(columns)
        record = DatasetRecord(
            id=dataset_id,
            filename=file.filename,
            stored_path=stored_path,
            columns=columns,
            mapping={},
            suggestions=suggestions,
        )
        dataset_store.add(record)

        return DatasetResponse(
            id=record.id,
            filename=record.filename,
            columns=record.columns,
            mapping=record.mapping,
            suggestions=record.suggestions,
        )

    @app.get("/datasets/{dataset_id}/mapping", response_model=DatasetResponse)
    async def get_mapping(dataset_id: str) -> DatasetResponse:
        try:
            record = dataset_store.get(dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        return DatasetResponse(
            id=record.id,
            filename=record.filename,
            columns=record.columns,
            mapping=record.mapping,
            suggestions=record.suggestions,
        )

    @app.put("/datasets/{dataset_id}/mapping", response_model=DatasetResponse)
    async def update_mapping(dataset_id: str, payload: UpdateMappingRequest) -> DatasetResponse:
        try:
            record = dataset_store.get(dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        valid_columns = {column.name for column in record.columns}
        invalid_keys = [key for key in payload.mapping.keys() if key not in valid_columns]
        if invalid_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown columns in mapping: {', '.join(invalid_keys)}",
            )

        updated = dataset_store.update_mapping(dataset_id, payload.mapping)

        return DatasetResponse(
            id=updated.id,
            filename=updated.filename,
            columns=updated.columns,
            mapping=updated.mapping,
            suggestions=updated.suggestions,
        )

    @app.post("/datasets/{dataset_id}/profile", response_model=DatasetProfileResponse, status_code=status.HTTP_202_ACCEPTED)
    async def trigger_profile(dataset_id: str, background_tasks: BackgroundTasks) -> DatasetProfileResponse:
        try:
            dataset_store.get(dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        cache_entry = profile_cache.start(dataset_id)
        background_tasks.add_task(run_profile_job, dataset_id)
        return build_profile_response(cache_entry, app)

    @app.get("/datasets/{dataset_id}/profile", response_model=DatasetProfileResponse)
    async def get_profile(dataset_id: str) -> DatasetProfileResponse:
        try:
            cache_entry = profile_cache.get(dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

        return build_profile_response(cache_entry, app)

    @app.get("/datasets/{dataset_id}/profile/artifact")
    async def download_profile_artifact(dataset_id: str) -> FileResponse:
        try:
            cache_entry = profile_cache.get(dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

        if not cache_entry.artifact_path or not cache_entry.artifact_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile artifact not found")

        return FileResponse(
            cache_entry.artifact_path,
            media_type="application/json",
            filename=cache_entry.artifact_path.name,
        )

    return app


app = get_app()
