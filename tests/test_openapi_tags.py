"""
tests/test_openapi_tags.py

Ensures all operation-level tags are declared in the global tags list.
"""
import pytest

from bazi_engine.app import app


@pytest.fixture(scope="module")
def schema():
    return app.openapi()


def test_all_operation_tags_defined_globally(schema):
    global_tags = {t["name"] for t in schema.get("tags", [])}
    errors = []
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            for tag in op.get("tags", []):
                if tag not in global_tags:
                    errors.append(f"{method.upper()} {path}: tag '{tag}' not in global tags")
    assert not errors, "Undeclared operation tags:\n" + "\n".join(errors)


def test_global_tags_non_empty(schema):
    global_tags = schema.get("tags", [])
    assert len(global_tags) >= 3, f"Expected at least 3 global tags, got {len(global_tags)}: {global_tags}"
