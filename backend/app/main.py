from __future__ import annotations

import csv
import shutil
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

    return app


app = get_app()
