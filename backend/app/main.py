from __future__ import annotations

import csv
import json
import random
import shutil
import threading
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pydantic import BaseModel, Field


DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DIR = DATA_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

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


class CreateModelRequest(BaseModel):
    name: str
    description: str | None = None
    task_type: Literal["classification", "regression"]


class ModelMetadata(BaseModel):
    id: str
    name: str
    description: str | None = None
    task_type: Literal["classification", "regression"]
    created_at: datetime
    latest_run_id: str | None = None


class ModelResponse(ModelMetadata):
    pass


class TrainingRequest(BaseModel):
    hyperparameters: dict[str, Any] = {}


class ModelRun(BaseModel):
    id: str
    model_id: str
    status: Literal["pending", "running", "succeeded", "failed"]
    created_at: datetime
    hyperparameters: dict[str, Any]
    metrics: dict[str, float] | None = None
    artifacts: list[str] = Field(default_factory=list)
    message: str | None = None


class RunListResponse(BaseModel):
    runs: list[ModelRun]


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


class ModelRecord(BaseModel):
    metadata: ModelMetadata
    runs: list[ModelRun] = Field(default_factory=list)


class ModelStore:
    def __init__(self) -> None:
        self._records: dict[str, ModelRecord] = {}
        self._lock = threading.Lock()

    def add(self, record: ModelRecord) -> None:
        with self._lock:
            self._records[record.metadata.id] = record

    def list_models(self) -> list[ModelRecord]:
        return list(self._records.values())

    def get(self, model_id: str) -> ModelRecord:
        if model_id not in self._records:
            raise KeyError(model_id)
        return self._records[model_id]

    def add_run(self, model_id: str, run: ModelRun) -> None:
        with self._lock:
            record = self.get(model_id)
            record.runs.append(run)
            record.metadata.latest_run_id = run.id
            self._records[model_id] = record

    def update_run(self, model_id: str, run: ModelRun) -> None:
        with self._lock:
            record = self.get(model_id)
            record.runs = [r if r.id != run.id else run for r in record.runs]
            record.metadata.latest_run_id = run.id
            self._records[model_id] = record

    def clear(self) -> None:
        with self._lock:
            self._records = {}


model_store = ModelStore()


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


def _get_run_dir(model_id: str, run_id: str) -> Path:
    return MODEL_DIR / model_id / "runs" / run_id


def _generate_learning_curve() -> list[dict[str, float]]:
    return [
        {"epoch": epoch, "train_loss": round(1.0 / (epoch + 1), 4), "val_loss": round(1.2 / (epoch + 1), 4)}
        for epoch in range(1, 6)
    ]


def _generate_metrics(task_type: Literal["classification", "regression"]) -> dict[str, float]:
    if task_type == "classification":
        base = random.uniform(0.75, 0.95)
        return {
            "train_accuracy": round(base, 3),
            "val_accuracy": round(base - random.uniform(0.02, 0.05), 3),
            "test_accuracy": round(base - random.uniform(0.01, 0.04), 3),
            "f1": round(base - random.uniform(0.03, 0.06), 3),
        }

    baseline = random.uniform(2.0, 5.0)
    return {
        "train_rmse": round(baseline, 3),
        "val_rmse": round(baseline + random.uniform(0.2, 1.0), 3),
        "test_rmse": round(baseline + random.uniform(0.1, 0.8), 3),
        "mae": round(baseline / random.uniform(1.3, 2.5), 3),
    }


def _write_artifacts(
    run_dir: Path,
    model: ModelMetadata,
    metrics: dict[str, float],
    hyperparameters: dict[str, Any],
) -> list[Path]:
    artifacts: list[Path] = []
    run_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    artifacts.append(metrics_path)

    hyperparameters_path = run_dir / "hyperparameters.json"
    hyperparameters_path.write_text(json.dumps(hyperparameters, indent=2), encoding="utf-8")
    artifacts.append(hyperparameters_path)

    model_path = run_dir / "model.txt"
    model_summary = {
        "model_id": model.id,
        "task_type": model.task_type,
        "created_at": model.created_at.isoformat(),
    }
    model_path.write_text(json.dumps(model_summary, indent=2), encoding="utf-8")
    artifacts.append(model_path)

    learning_curve_path = run_dir / "learning_curve.csv"
    learning_curve = _generate_learning_curve()
    with learning_curve_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["epoch", "train_loss", "val_loss"])
        writer.writeheader()
        writer.writerows(learning_curve)
    artifacts.append(learning_curve_path)

    return artifacts


def _train_model(model_id: str, run_id: str) -> None:
    try:
        record = model_store.get(model_id)
    except KeyError:
        return

    run = next((r for r in record.runs if r.id == run_id), None)
    if not run:
        return

    run.status = "running"
    model_store.update_run(model_id, run)

    try:
        metrics = _generate_metrics(record.metadata.task_type)
        artifacts = _write_artifacts(
            _get_run_dir(model_id, run_id),
            record.metadata,
            metrics,
            run.hyperparameters,
        )
        run.metrics = metrics
        run.artifacts = [path.name for path in artifacts]
        run.status = "succeeded"
        run.message = "Training completed successfully"
    except Exception as exc:  # pragma: no cover - defensive
        run.status = "failed"
        run.message = str(exc)

    model_store.update_run(model_id, run)


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

    @app.post("/models", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
    def create_model(payload: CreateModelRequest) -> ModelResponse:
        model_id = str(uuid4())
        metadata = ModelMetadata(
            id=model_id,
            name=payload.name,
            description=payload.description,
            task_type=payload.task_type,
            created_at=datetime.utcnow(),
        )

        model_dir = MODEL_DIR / model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "metadata.json").write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

        model_store.add(ModelRecord(metadata=metadata))
        return metadata

    @app.get("/models", response_model=list[ModelResponse])
    def list_models() -> list[ModelResponse]:
        return [record.metadata for record in model_store.list_models()]

    @app.get("/models/{model_id}", response_model=ModelResponse)
    def get_model(model_id: str) -> ModelResponse:
        try:
            record = model_store.get(model_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        return record.metadata

    @app.post("/models/{model_id}/train", response_model=ModelRun, status_code=status.HTTP_202_ACCEPTED)
    def start_training(model_id: str, payload: TrainingRequest) -> ModelRun:
        try:
            model_store.get(model_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

        run_id = str(uuid4())
        run = ModelRun(
            id=run_id,
            model_id=model_id,
            status="pending",
            created_at=datetime.utcnow(),
            hyperparameters=payload.hyperparameters,
        )
        model_store.add_run(model_id, run)

        thread = threading.Thread(target=_train_model, args=(model_id, run_id), daemon=True)
        thread.start()

        return run

    @app.get("/models/{model_id}/runs", response_model=RunListResponse)
    def get_runs(model_id: str) -> RunListResponse:
        try:
            record = model_store.get(model_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        return RunListResponse(runs=record.runs)

    @app.get("/models/{model_id}/runs/{run_id}", response_model=ModelRun)
    def get_run(model_id: str, run_id: str) -> ModelRun:
        try:
            record = model_store.get(model_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

        for run in record.runs:
            if run.id == run_id:
                return run

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    @app.get("/models/{model_id}/runs/{run_id}/artifacts/{artifact_name}")
    def download_artifact(model_id: str, run_id: str, artifact_name: str):
        artifact_path = _get_run_dir(model_id, run_id) / artifact_name
        if not artifact_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
        return FileResponse(path=artifact_path, filename=artifact_path.name)

    return app


app = get_app()
