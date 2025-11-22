from __future__ import annotations

import csv
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


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


class AuditLogEntry(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    status: str
    message: str | None = None
    retries: int = 0
    timestamp: datetime


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobRecord(BaseModel):
    id: str
    name: str
    entity_type: str
    entity_id: str
    status: JobStatus
    retries: int = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TargetRequest(BaseModel):
    dataset_id: str
    target: str


class ModelTrainRequest(BaseModel):
    dataset_id: str
    target: str
    force_error: bool = False


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


class AuditLogStore:
    def __init__(self) -> None:
        self._entries: list[AuditLogEntry] = []

    def add(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        status: str,
        message: str | None = None,
        retries: int = 0,
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            id=str(uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            status=status,
            message=message,
            retries=retries,
            timestamp=datetime.utcnow(),
        )
        self._entries.append(entry)
        return entry

    def list(self, limit: int = 50) -> list[AuditLogEntry]:
        return list(reversed(self._entries))[:limit]


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create(self, name: str, entity_type: str, entity_id: str) -> JobRecord:
        now = datetime.utcnow()
        job = JobRecord(
            id=str(uuid4()),
            name=name,
            entity_type=entity_type,
            entity_id=entity_id,
            status=JobStatus.RUNNING,
            created_at=now,
            updated_at=now,
        )
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> JobRecord:
        if job_id not in self._jobs:
            raise KeyError(job_id)
        return self._jobs[job_id]

    def list(self) -> list[JobRecord]:
        return sorted(self._jobs.values(), key=lambda job: job.updated_at, reverse=True)

    def complete(self, job_id: str, *, success: bool, error_message: str | None = None) -> JobRecord:
        job = self.get(job_id)
        job.status = JobStatus.SUCCEEDED if success else JobStatus.FAILED
        job.error_message = error_message
        job.updated_at = datetime.utcnow()
        self._jobs[job_id] = job
        return job

    def retry(self, job_id: str) -> JobRecord:
        job = self.get(job_id)
        job.retries += 1
        job.status = JobStatus.RUNNING
        job.error_message = None
        job.updated_at = datetime.utcnow()
        self._jobs[job_id] = job
        return job


audit_log_store = AuditLogStore()
job_store = JobStore()


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

        audit_log_store.add(
            entity_type="dataset",
            entity_id=record.id,
            action="upload",
            status="completed",
            message=f"Uploaded dataset {record.filename}",
        )

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

        audit_log_store.add(
            entity_type="dataset",
            entity_id=updated.id,
            action="update_mapping",
            status="completed",
            message="Updated dataset mapping",
        )

        return DatasetResponse(
            id=updated.id,
            filename=updated.filename,
            columns=updated.columns,
            mapping=updated.mapping,
            suggestions=updated.suggestions,
        )

    @app.post("/targets", response_model=JobRecord)
    async def set_target(request: TargetRequest) -> JobRecord:
        try:
            record = dataset_store.get(request.dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        job = job_store.create(name="Validate target", entity_type="target", entity_id=request.dataset_id)

        column_names = {column.name for column in record.columns}
        if request.target not in column_names:
            failed_job = job_store.complete(
                job.id, success=False, error_message=f"Target '{request.target}' not found in dataset"
            )
            audit_log_store.add(
                entity_type="target",
                entity_id=request.dataset_id,
                action="set_target",
                status="failed",
                message=failed_job.error_message,
                retries=failed_job.retries,
            )
            return failed_job

        completed_job = job_store.complete(job.id, success=True)
        audit_log_store.add(
            entity_type="target",
            entity_id=request.dataset_id,
            action="set_target",
            status="completed",
            message=f"Target column set to '{request.target}'",
            retries=completed_job.retries,
        )
        return completed_job

    @app.post("/models/train", response_model=JobRecord)
    async def train_model(request: ModelTrainRequest) -> JobRecord:
        try:
            record = dataset_store.get(request.dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        job = job_store.create(name="Train model", entity_type="model", entity_id=request.dataset_id)

        if request.target not in {column.name for column in record.columns}:
            failed_job = job_store.complete(
                job.id, success=False, error_message=f"Target '{request.target}' not found in dataset"
            )
            audit_log_store.add(
                entity_type="model",
                entity_id=request.dataset_id,
                action="train",
                status="failed",
                message=failed_job.error_message,
                retries=failed_job.retries,
            )
            return failed_job

        if request.force_error:
            failed_job = job_store.complete(job.id, success=False, error_message="Training job failed")
            audit_log_store.add(
                entity_type="model",
                entity_id=request.dataset_id,
                action="train",
                status="failed",
                message=failed_job.error_message,
                retries=failed_job.retries,
            )
            return failed_job

        completed_job = job_store.complete(job.id, success=True)
        audit_log_store.add(
            entity_type="model",
            entity_id=request.dataset_id,
            action="train",
            status="completed",
            message="Model training completed",
            retries=completed_job.retries,
        )
        return completed_job

    @app.post("/jobs/{job_id}/retry", response_model=JobRecord)
    async def retry_job(job_id: str) -> JobRecord:
        try:
            job = job_store.get(job_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        if job.status != JobStatus.FAILED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed jobs can be retried")

        job_store.retry(job_id)
        completed = job_store.complete(job_id, success=True)
        audit_log_store.add(
            entity_type=job.entity_type,
            entity_id=job.entity_id,
            action="retry",
            status=completed.status.value,
            retries=completed.retries,
            message="Job retried",
        )
        return completed

    @app.get("/audit/logs", response_model=list[AuditLogEntry])
    async def list_audit_logs() -> list[AuditLogEntry]:
        return audit_log_store.list()

    @app.get("/jobs", response_model=list[JobRecord])
    async def list_jobs() -> list[JobRecord]:
        return job_store.list()

    return app


app = get_app()
