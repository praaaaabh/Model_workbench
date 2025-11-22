from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
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
    standardized_path: Path | None = None
    columns: list[ColumnSchema]
    mapping: dict[str, str]
    suggestions: dict[str, str]
    column_types: dict[str, str]
    standardization_status: "StandardizationStatus | None" = None


class DatasetResponse(BaseModel):
    id: str
    filename: str
    columns: list[ColumnSchema]
    mapping: dict[str, str]
    suggestions: dict[str, str]
    column_types: dict[str, str]
    standardization_status: "StandardizationStatus | None" = None


class UpdateMappingRequest(BaseModel):
    mapping: dict[str, str]


class StandardizeRequest(BaseModel):
    column_types: dict[str, str]


class ErrorSample(BaseModel):
    row: int
    column: str
    value: str
    error: str


class StandardizationStatus(BaseModel):
    status: str
    progress: int
    message: str | None = None
    rows_total: int = 0
    rows_processed: int = 0
    rows_with_errors: int = 0
    error_samples: list[ErrorSample] = Field(default_factory=list)
    output_filename: str | None = None
    audit_log: list[str] = Field(default_factory=list)


DatasetRecord.model_rebuild()
DatasetResponse.model_rebuild()


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

    def update_column_types(self, dataset_id: str, column_types: dict[str, str]) -> DatasetRecord:
        record = self.get(dataset_id)
        record.column_types = column_types
        self._records[dataset_id] = record
        return record

    def set_status(self, dataset_id: str, status: StandardizationStatus) -> StandardizationStatus:
        record = self.get(dataset_id)
        record.standardization_status = status
        self._records[dataset_id] = record
        return status

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


def _convert_value(value: str, target_type: str) -> tuple[str | int | float, str | None]:
    if value == "":
        return "", None

    try:
        if target_type == "integer":
            return int(value), None
        if target_type == "float":
            return float(value), None
    except ValueError as error:  # pragma: no cover - handled by error path
        return value, str(error)

    return value, None


def standardize_dataset(record: DatasetRecord, column_types: dict[str, str]) -> StandardizationStatus:
    status = StandardizationStatus(
        status="running",
        progress=0,
        message="Starting standardization",
        audit_log=["Standardization started"],
    )
    dataset_store.set_status(record.id, status)

    try:
        output_path = DATA_DIR / f"{record.id}_standardized.csv"
        error_samples: list[ErrorSample] = []
        rows_processed = 0
        rows_with_errors = 0

        with record.stored_path.open("r", newline="", encoding="utf-8") as source, output_path.open(
            "w", newline="", encoding="utf-8"
        ) as target:
            reader = csv.DictReader(source)
            if reader.fieldnames is None:
                raise ValueError("Unable to read CSV header for standardization")

            unknown_columns = [name for name in column_types.keys() if name not in reader.fieldnames]
            if unknown_columns:
                raise ValueError(f"Unknown columns in column_types: {', '.join(unknown_columns)}")

            fieldnames = [record.mapping.get(name, name) for name in reader.fieldnames]
            writer = csv.DictWriter(target, fieldnames=fieldnames)
            writer.writeheader()

            for row_index, row in enumerate(reader, start=1):
                rows_processed += 1
                converted_row: dict[str, str | int | float] = {}

                for original_name, value in row.items():
                    target_name = record.mapping.get(original_name, original_name)
                    target_type = column_types.get(original_name, record.column_types.get(original_name, "string"))
                    converted, error = _convert_value(value or "", target_type)

                    if error and len(error_samples) < 5:
                        error_samples.append(
                            ErrorSample(
                                row=row_index,
                                column=original_name,
                                value=value or "",
                                error=error,
                            )
                        )
                    if error:
                        rows_with_errors += 1

                    converted_row[target_name] = converted

                writer.writerow(converted_row)

        status = StandardizationStatus(
            status="completed",
            progress=100,
            message="Standardization finished",
            rows_total=rows_processed,
            rows_processed=rows_processed,
            rows_with_errors=rows_with_errors,
            error_samples=error_samples,
            output_filename=output_path.name,
            audit_log=["Standardization completed"],
        )
        dataset_store.update_column_types(record.id, column_types)
        dataset_store.set_status(record.id, status)
        record.standardization_status = status
        record.standardized_path = output_path if hasattr(record, "standardized_path") else output_path
        return status
    except Exception as exc:  # pragma: no cover - defensive programming
        failure_status = StandardizationStatus(
            status="failed",
            progress=100,
            message=str(exc),
            rows_total=status.rows_total,
            rows_processed=status.rows_processed,
            rows_with_errors=status.rows_with_errors,
            error_samples=status.error_samples,
            output_filename=status.output_filename,
            audit_log=status.audit_log + [f"Failed: {exc}"],
        )
        dataset_store.set_status(record.id, failure_status)
        return failure_status


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
            standardized_path=None,
            columns=columns,
            mapping={},
            suggestions=suggestions,
            column_types={column.name: column.inferred_type for column in columns},
            standardization_status=None,
        )
        dataset_store.add(record)

        return DatasetResponse(
            id=record.id,
            filename=record.filename,
            columns=record.columns,
            mapping=record.mapping,
            suggestions=record.suggestions,
            column_types=record.column_types,
            standardization_status=record.standardization_status,
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
            column_types=record.column_types,
            standardization_status=record.standardization_status,
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
            column_types=updated.column_types,
            standardization_status=updated.standardization_status,
        )

    @app.post("/datasets/{dataset_id}/standardize", response_model=StandardizationStatus)
    async def standardize(dataset_id: str, payload: StandardizeRequest) -> StandardizationStatus:
        try:
            record = dataset_store.get(dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        valid_columns = {column.name for column in record.columns}
        invalid = [name for name in payload.column_types.keys() if name not in valid_columns]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown columns in column_types: {', '.join(invalid)}",
            )

        status_result = standardize_dataset(record, payload.column_types)
        return status_result

    @app.get("/datasets/{dataset_id}/standardize/status", response_model=StandardizationStatus)
    async def get_standardization_status(dataset_id: str) -> StandardizationStatus:
        try:
            record = dataset_store.get(dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        if record.standardization_status:
            return record.standardization_status

        return StandardizationStatus(
            status="pending",
            progress=0,
            message="No standardization has been run",
            audit_log=[],
        )

    return app


app = get_app()
