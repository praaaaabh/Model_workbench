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
    version: int
    columns: list[ColumnSchema]
    mapping: dict[str, str]
    suggestions: dict[str, str]


class DatasetResponse(BaseModel):
    id: str
    filename: str
    version: int
    columns: list[ColumnSchema]
    mapping: dict[str, str]
    suggestions: dict[str, str]


class UpdateMappingRequest(BaseModel):
    mapping: dict[str, str]


class Rule(BaseModel):
    column: str
    operator: str
    value: str


class Recipe(BaseModel):
    target_name: str
    rules: list[Rule]
    filters: list[Rule] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {"examples": [{"target_name": "target", "rules": [], "filters": []}]}
    }


class CreateTargetRequest(BaseModel):
    dataset_id: str
    dataset_version: int
    recipe: Recipe


class TargetRecord(BaseModel):
    id: str
    dataset_id: str
    dataset_version: int
    recipe: Recipe


class TargetResponse(BaseModel):
    id: str
    dataset_id: str
    dataset_version: int
    recipe: Recipe


class MaterializeResponse(BaseModel):
    target_id: str
    dataset_id: str
    dataset_version: int
    output_filename: str
    row_count: int
    preview: list[dict[str, str]]


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
        record.version += 1
        self._records[dataset_id] = record
        return record

    def clear(self) -> None:
        self._records = {}


class TargetStore:
    def __init__(self) -> None:
        self._records: dict[str, TargetRecord] = {}

    def add(self, record: TargetRecord) -> None:
        self._records[record.id] = record

    def get(self, target_id: str) -> TargetRecord:
        if target_id not in self._records:
            raise KeyError(target_id)
        return self._records[target_id]

    def clear(self) -> None:
        self._records = {}


dataset_store = DatasetStore()
target_store = TargetStore()


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


def _validate_recipe_columns(recipe: Recipe, columns: list[ColumnSchema]) -> None:
    available = {column.name for column in columns}
    for rule in [*recipe.rules, *recipe.filters]:
        if rule.column not in available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Column '{rule.column}' is not present in the dataset",
            )


def _coerce_numeric(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _evaluate_rule(rule: Rule, row: dict[str, str]) -> bool:
    raw_value = row.get(rule.column, "")
    operator = rule.operator
    expected = rule.value

    if operator == "exists":
        return raw_value is not None and str(raw_value).strip() != ""

    if operator in {"gt", "gte", "lt", "lte"}:
        left = _coerce_numeric(str(raw_value))
        right = _coerce_numeric(expected)
        if left is None or right is None:
            return False
        if operator == "gt":
            return left > right
        if operator == "gte":
            return left >= right
        if operator == "lt":
            return left < right
        return left <= right

    if operator == "equals":
        return str(raw_value) == expected
    if operator == "not_equals":
        return str(raw_value) != expected
    if operator == "contains":
        return expected.lower() in str(raw_value).lower()

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported operator: {operator}")


def _materialize_target(dataset: DatasetRecord, target: TargetRecord) -> MaterializeResponse:
    output_filename = f"{dataset.id}_target_{target.id}.csv"
    output_path = DATA_DIR / output_filename

    with dataset.stored_path.open("r", newline="", encoding="utf-8") as source, output_path.open(
        "w", newline="", encoding="utf-8"
    ) as destination:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset has no columns")

        fieldnames = reader.fieldnames + [target.recipe.target_name]
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()

        row_count = 0
        preview: list[dict[str, str]] = []
        for row in reader:
            filters_pass = all(_evaluate_rule(rule, row) for rule in target.recipe.filters)
            result_value = ""
            if filters_pass:
                meets_rules = all(_evaluate_rule(rule, row) for rule in target.recipe.rules)
                result_value = "1" if meets_rules else "0"

            row[target.recipe.target_name] = result_value
            writer.writerow(row)
            row_count += 1
            if len(preview) < 5:
                preview.append(row.copy())

    return MaterializeResponse(
        target_id=target.id,
        dataset_id=dataset.id,
        dataset_version=dataset.version,
        output_filename=output_filename,
        row_count=row_count,
        preview=preview,
    )


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
            version=1,
            stored_path=stored_path,
            columns=columns,
            mapping={},
            suggestions=suggestions,
        )
        dataset_store.add(record)

        return DatasetResponse(
            id=record.id,
            filename=record.filename,
            version=record.version,
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
            version=record.version,
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
            version=updated.version,
            columns=updated.columns,
            mapping=updated.mapping,
            suggestions=updated.suggestions,
        )

    @app.post("/targets", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
    async def create_target(payload: CreateTargetRequest) -> TargetResponse:
        try:
            dataset = dataset_store.get(payload.dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        if payload.dataset_version != dataset.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dataset version mismatch. Please reload the dataset before creating a target.",
            )

        _validate_recipe_columns(payload.recipe, dataset.columns)

        record = TargetRecord(
            id=str(uuid4()),
            dataset_id=dataset.id,
            dataset_version=dataset.version,
            recipe=payload.recipe,
        )
        target_store.add(record)

        return TargetResponse(
            id=record.id,
            dataset_id=record.dataset_id,
            dataset_version=record.dataset_version,
            recipe=record.recipe,
        )

    @app.post("/targets/{target_id}/materialize", response_model=MaterializeResponse)
    async def materialize_target(target_id: str) -> MaterializeResponse:
        try:
            target = target_store.get(target_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

        try:
            dataset = dataset_store.get(target.dataset_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        if dataset.version != target.dataset_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dataset has changed since this target was created. Please recreate the target.",
            )

        _validate_recipe_columns(target.recipe, dataset.columns)

        return _materialize_target(dataset, target)

    return app


app = get_app()
