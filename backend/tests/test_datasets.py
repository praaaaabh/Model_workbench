from fastapi.testclient import TestClient

from app.main import app, dataset_store


def setup_function() -> None:
    dataset_store.clear()


def test_create_dataset_infers_schema() -> None:
    client = TestClient(app)
    file_content = "age,height,weight\n30,170,70\n25,160,55\n"

    response = client.post(
        "/datasets",
        files={"file": ("sample.csv", file_content, "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["filename"] == "sample.csv"
    assert payload["columns"] == [
        {"name": "age", "inferred_type": "integer"},
        {"name": "height", "inferred_type": "integer"},
        {"name": "weight", "inferred_type": "integer"},
    ]
    assert payload["mapping"] == {}
    assert payload["suggestions"]["age"] == "age"


def test_update_and_fetch_mapping() -> None:
    client = TestClient(app)
    file_content = "patient_id,glucose\n123,90.5\n124,88.2\n"

    create_response = client.post(
        "/datasets",
        files={"file": ("sample.csv", file_content, "text/csv")},
    )
    dataset_id = create_response.json()["id"]

    mapping_response = client.get(f"/datasets/{dataset_id}/mapping")
    assert mapping_response.status_code == 200
    mapping_payload = mapping_response.json()
    assert mapping_payload["suggestions"]["patient_id"] == "patient_id"

    update_response = client.put(
        f"/datasets/{dataset_id}/mapping",
        json={"mapping": {"patient_id": "patient_identifier", "glucose": "fasting_glucose"}},
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["mapping"] == {
        "patient_id": "patient_identifier",
        "glucose": "fasting_glucose",
    }

    round_trip = client.get(f"/datasets/{dataset_id}/mapping")
    assert round_trip.json()["mapping"]["glucose"] == "fasting_glucose"


def test_standardize_dataset_tracks_status_and_errors() -> None:
    client = TestClient(app)
    file_content = "age,height\n30,170\nunknown,abc\n"

    create_response = client.post(
        "/datasets",
        files={"file": ("sample.csv", file_content, "text/csv")},
    )
    dataset_id = create_response.json()["id"]

    standardize_response = client.post(
        f"/datasets/{dataset_id}/standardize",
        json={"column_types": {"age": "integer", "height": "float"}},
    )

    assert standardize_response.status_code == 200
    payload = standardize_response.json()
    assert payload["status"] == "completed"
    assert payload["rows_total"] == 2
    assert payload["rows_with_errors"] >= 1
    assert payload["output_filename"].endswith("_standardized.csv")
    assert len(payload["error_samples"]) >= 1

    status_response = client.get(f"/datasets/{dataset_id}/standardize/status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["rows_processed"] == 2
