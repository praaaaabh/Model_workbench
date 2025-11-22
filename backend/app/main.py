from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel


DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
SCORES_DIR = DATA_DIR / "scores"
SCORES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL_ID = "demo-model"

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


class ScoreRequest(BaseModel):
    dataset_id: str


class ScoreResponse(BaseModel):
    model_id: str
    dataset_id: str
    scored_filename: str
    scored_file_url: str


class ModelArtifact(BaseModel):
    name: str
    path: Path
    kind: str


class ArtifactInfo(BaseModel):
    name: str
    kind: str
    url: str


class ModelRecord(BaseModel):
    id: str
    name: str
    artifacts: list[ModelArtifact]


class ModelArtifactsResponse(BaseModel):
    id: str
    name: str
    artifacts: list[ArtifactInfo]


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


class ModelStore:
    def __init__(self) -> None:
        self._records: dict[str, ModelRecord] = {}

    def add(self, record: ModelRecord) -> None:
        self._records[record.id] = record

    def get(self, model_id: str) -> ModelRecord:
        if model_id not in self._records:
            raise KeyError(model_id)
        return self._records[model_id]

    def clear(self) -> None:
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


def save_upload_file(upload_file: UploadFile, dataset_id: str) -> Path:
    stored_name = f"{dataset_id}_{upload_file.filename}"
    stored_path = DATA_DIR / stored_name
    with stored_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return stored_path


def seed_default_model() -> None:
    model_dir = MODELS_DIR / DEFAULT_MODEL_ID
    model_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "model.bin": (model_dir / "model.bin", b"demo model binary"),
        "metrics.json": (
            model_dir / "metrics.json",
            json.dumps({"accuracy": 0.84, "auc": 0.77}, indent=2).encode("utf-8"),
        ),
        "roc.png": (model_dir / "roc.png", b"demo plot placeholder"),
    }

    for name, (path, content) in artifacts.items():
        if not path.exists():
            path.write_bytes(content)

    artifact_models = [
        ModelArtifact(name="model.bin", path=model_dir / "model.bin", kind="model_binary"),
        ModelArtifact(name="metrics.json", path=model_dir / "metrics.json", kind="metrics"),
        ModelArtifact(name="roc.png", path=model_dir / "roc.png", kind="plot"),
    ]

    model_store.add(
        ModelRecord(id=DEFAULT_MODEL_ID, name="Demo classification model", artifacts=artifact_models)
    )


def get_artifact_download_path(model_id: str, artifact_name: str) -> str:
    return f"/models/{model_id}/artifacts/{artifact_name}"


def build_scored_file_name(dataset_id: str, model_id: str) -> str:
    return f"{dataset_id}_{model_id}_scored.csv"


def generate_scored_file(dataset: DatasetRecord, model_id: str) -> Path:
    scored_file = SCORES_DIR / build_scored_file_name(dataset.id, model_id)

    with dataset.stored_path.open("r", newline="", encoding="utf-8") as source, scored_file.open(
        "w", newline="", encoding="utf-8"
    ) as target:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset is missing a header row"
            )

        fieldnames = reader.fieldnames + ["score"]
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()

        for index, row in enumerate(reader):
            row["score"] = round(0.6 + (index % 5) * 0.05, 2)
            writer.writerow(row)

    return scored_file


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

    seed_default_model()

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

    @app.get("/models/{model_id}/artifacts", response_model=ModelArtifactsResponse)
    async def list_model_artifacts(model_id: str) -> ModelArtifactsResponse:
        try:
            record = model_store.get(model_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

        artifacts = [
            ArtifactInfo(name=artifact.name, kind=artifact.kind, url=get_artifact_download_path(model_id, artifact.name))
            for artifact in record.artifacts
        ]

        return ModelArtifactsResponse(id=record.id, name=record.name, artifacts=artifacts)

    @app.get("/models/{model_id}/artifacts/{artifact_name}")
    async def download_model_artifact(model_id: str, artifact_name: str) -> FileResponse:
        try:
            record = model_store.get(model_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

        matching = [artifact for artifact in record.artifacts if artifact.name == artifact_name]
        if not matching:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        artifact = matching[0]
        if not artifact.path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file missing")

        media_type = "application/octet-stream"
        if artifact.path.suffix == ".json":
            media_type = "application/json"
        elif artifact.path.suffix == ".png":
            media_type = "image/png"

        return FileResponse(path=artifact.path, media_type=media_type, filename=artifact.name)

    @app.post("/models/{model_id}/score", response_model=ScoreResponse)
    async def score_dataset(model_id: str, payload: ScoreRequest) -> ScoreResponse:
        try:
            dataset = dataset_store.get(payload.dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        try:
            model_store.get(model_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

        scored_file = generate_scored_file(dataset, model_id)
        scored_url = f"/models/{model_id}/scores/{scored_file.name}"

        return ScoreResponse(
            model_id=model_id,
            dataset_id=dataset.id,
            scored_filename=scored_file.name,
            scored_file_url=scored_url,
        )

    @app.get("/models/{model_id}/scores/{score_filename}")
    async def download_scored_file(model_id: str, score_filename: str) -> FileResponse:
        expected_suffix = f"_{model_id}_scored.csv"
        if not score_filename.endswith(expected_suffix):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scored file not found")

        target_path = SCORES_DIR / score_filename
        if not target_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scored file not found")

        return FileResponse(path=target_path, media_type="text/csv", filename=score_filename)

    return app


app = get_app()
