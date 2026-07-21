"""CI guards for the key-store backend architecture policy."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_RUNTIME_IMPORT_PATTERNS = (
    "from google.cloud import firestore",
    "import google.cloud.firestore",
)


def test_firestore_backend_policy_is_enforced() -> None:
    """Firestore must remain unsupported and absent from runtime imports/deps."""
    for relative_path in ("pyproject.toml", "requirements.lock", "requirements.txt"):
        path = REPO_ROOT / relative_path
        if path.exists():
            assert "google-cloud-firestore" not in path.read_text(encoding="utf-8")

    runtime_files = sorted((REPO_ROOT / "bazi_engine").rglob("*.py"))
    assert runtime_files, "expected bazi_engine runtime files to exist"
    for path in runtime_files:
        source = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_RUNTIME_IMPORT_PATTERNS:
            assert pattern not in source, f"forbidden Firestore import in {path.relative_to(REPO_ROOT)}"

    key_store_source = (REPO_ROOT / "bazi_engine" / "key_store.py").read_text(encoding="utf-8")
    assert "FirestoreKeyStore" not in key_store_source
    assert "firestore —" not in key_store_source
    assert "none, memory, firestore" not in key_store_source
    assert "Supported backends: none, memory" in key_store_source
