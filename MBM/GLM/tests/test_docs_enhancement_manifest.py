import json
from pathlib import Path


def test_enhancement_manifest_is_bounded():
    path = Path(__file__).resolve().parent.parent / "docs_enhancement_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["enhancements"]) >= 10
    assert data["rollout"] == [
        "contracts",
        "tests",
        "feature_flags",
        "sandbox_evals",
        "staged_adoption",
        "promotion_gate",
    ]


def test_every_enhancement_has_guard():
    path = Path(__file__).resolve().parent.parent / "docs_enhancement_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert all(item.get("guard") for item in data["enhancements"])
