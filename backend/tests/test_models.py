from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import (
    DEFAULT_MODEL_ID,
    SCORES_DIR,
    app,
    dataset_store,
    model_store,
    seed_default_model,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state() -> None:
    dataset_store.clear()
    model_store.clear()
    seed_default_model()

    for scored_file in SCORES_DIR.glob("*_scored.csv"):
        scored_file.unlink()

    yield

    dataset_store.clear()


def test_score_dataset_returns_download_url(tmp_path: Path) -> None:
    dataset_path = tmp_path / "sample.csv"
    dataset_path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    with dataset_path.open("rb") as handle:
        response = client.post("/datasets", files={"file": ("sample.csv", handle, "text/csv")})

    assert response.status_code == 201
    dataset_id = response.json()["id"]

    score_response = client.post(f"/models/{DEFAULT_MODEL_ID}/score", json={"dataset_id": dataset_id})
    assert score_response.status_code == 200

    payload = score_response.json()
    assert payload["scored_file_url"].endswith("_scored.csv")

    download_response = client.get(payload["scored_file_url"])
    assert download_response.status_code == 200
    assert download_response.text.splitlines()[0].endswith(",score")


def test_model_artifacts_can_be_downloaded() -> None:
    response = client.get(f"/models/{DEFAULT_MODEL_ID}/artifacts")
    assert response.status_code == 200

    payload = response.json()
    assert len(payload["artifacts"]) >= 1

    first_artifact_url = payload["artifacts"][0]["url"]
    download_response = client.get(first_artifact_url)
    assert download_response.status_code == 200
    assert download_response.content
