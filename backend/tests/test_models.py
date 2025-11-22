import shutil
import time

from fastapi.testclient import TestClient

from app.main import MODEL_DIR, app, model_store


def setup_function() -> None:
    model_store.clear()
    if MODEL_DIR.exists():
        shutil.rmtree(MODEL_DIR)
        MODEL_DIR.mkdir(parents=True, exist_ok=True)


def test_create_model_and_list() -> None:
    client = TestClient(app)
    response = client.post(
        "/models",
        json={"name": "Heart Classifier", "description": "demo", "task_type": "classification"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Heart Classifier"
    assert payload["task_type"] == "classification"

    list_response = client.get("/models")
    assert list_response.status_code == 200
    assert any(model["id"] == payload["id"] for model in list_response.json())


def test_train_model_creates_run_and_artifacts() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/models",
        json={"name": "Regressor", "description": "demo", "task_type": "regression"},
    )
    model_id = create_response.json()["id"]

    train_response = client.post(
        f"/models/{model_id}/train",
        json={"hyperparameters": {"learning_rate": 0.01, "epochs": 5}},
    )

    assert train_response.status_code == 202
    run_id = train_response.json()["id"]

    status = None
    for _ in range(10):
        runs_response = client.get(f"/models/{model_id}/runs")
        assert runs_response.status_code == 200
        run_payload = next(run for run in runs_response.json()["runs"] if run["id"] == run_id)
        status = run_payload["status"]
        if status == "succeeded":
            assert run_payload["metrics"]
            assert any(artifact.endswith("metrics.json") for artifact in run_payload["artifacts"])
            break
        time.sleep(0.1)

    assert status == "succeeded"

    artifact_name = next(name for name in client.get(f"/models/{model_id}/runs").json()["runs"][0]["artifacts"])
    download = client.get(f"/models/{model_id}/runs/{run_id}/artifacts/{artifact_name}")
    assert download.status_code == 200
    assert download.content
