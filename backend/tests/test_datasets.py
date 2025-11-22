import time

from fastapi.testclient import TestClient

from app.main import app, dataset_store, profile_cache


def setup_function() -> None:
    dataset_store.clear()
    profile_cache.clear()


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


def test_profile_generation_and_artifact_download() -> None:
    client = TestClient(app)
    file_content = "age,height,weight\n30,170,70\n25,160,55\n"

    create_response = client.post(
        "/datasets",
        files={"file": ("sample.csv", file_content, "text/csv")},
    )
    dataset_id = create_response.json()["id"]

    trigger = client.post(f"/datasets/{dataset_id}/profile")
    assert trigger.status_code == 202
    assert trigger.json()["status"] == "pending"

    profile = None
    for _ in range(5):
        profile_response = client.get(f"/datasets/{dataset_id}/profile")
        profile = profile_response.json()
        if profile["status"] != "pending":
            break
        time.sleep(0.01)

    assert profile is not None
    assert profile["status"] == "completed"
    assert profile["row_count"] == 2
    assert profile["column_count"] == 3
    assert profile["artifact_url"]

    artifact_response = client.get(profile["artifact_url"])
    assert artifact_response.status_code == 200
    payload = artifact_response.json()
    assert payload["row_count"] == 2
    assert len(payload["columns"]) == 3
