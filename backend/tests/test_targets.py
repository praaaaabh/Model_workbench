from fastapi.testclient import TestClient

from app.main import app, dataset_store, target_store


def setup_function() -> None:
    dataset_store.clear()
    target_store.clear()


def _create_dataset(client: TestClient) -> dict:
    file_content = "patient_id,glucose,age\n123,90.5,30\n124,100.2,25\n125,85.0,40\n"
    response = client.post(
        "/datasets",
        files={"file": ("sample.csv", file_content, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()


def test_create_target_with_recipe() -> None:
    client = TestClient(app)
    dataset = _create_dataset(client)

    payload = {
        "dataset_id": dataset["id"],
        "dataset_version": dataset["version"],
        "recipe": {
            "target_name": "high_glucose",
            "rules": [{"column": "glucose", "operator": "gt", "value": "95"}],
            "filters": [],
        },
    }

    response = client.post("/targets", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["dataset_id"] == dataset["id"]
    assert body["dataset_version"] == dataset["version"]
    assert body["recipe"]["target_name"] == "high_glucose"


def test_materialize_target_generates_column() -> None:
    client = TestClient(app)
    dataset = _create_dataset(client)

    recipe_payload = {
        "dataset_id": dataset["id"],
        "dataset_version": dataset["version"],
        "recipe": {
            "target_name": "is_high_glucose",
            "rules": [{"column": "glucose", "operator": "gt", "value": "95"}],
            "filters": [{"column": "age", "operator": "gte", "value": "25"}],
        },
    }

    create_response = client.post("/targets", json=recipe_payload)
    target_id = create_response.json()["id"]

    materialize_response = client.post(f"/targets/{target_id}/materialize")
    assert materialize_response.status_code == 200

    body = materialize_response.json()
    assert body["row_count"] == 3
    assert body["output_filename"].endswith(f"{target_id}.csv")
    preview = body["preview"]
    assert preview[0]["is_high_glucose"] == "0"
    assert preview[1]["is_high_glucose"] == "1"


def test_materialize_rejects_outdated_version() -> None:
    client = TestClient(app)
    dataset = _create_dataset(client)

    recipe_payload = {
        "dataset_id": dataset["id"],
        "dataset_version": dataset["version"],
        "recipe": {
            "target_name": "is_high_glucose",
            "rules": [{"column": "glucose", "operator": "gt", "value": "95"}],
            "filters": [],
        },
    }

    create_response = client.post("/targets", json=recipe_payload)
    target_id = create_response.json()["id"]

    # mutate dataset version
    client.put(
        f"/datasets/{dataset['id']}/mapping",
        json={"mapping": {"patient_id": "patient_identifier"}},
    )

    conflict_response = client.post(f"/targets/{target_id}/materialize")
    assert conflict_response.status_code == 409
    assert "Dataset has changed" in conflict_response.json()["detail"]
