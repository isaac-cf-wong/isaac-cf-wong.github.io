"""Validation of content files against their JSON Schemas.

Each content file ``<name>.yaml`` is checked against ``<name>.schema.json`` in
the schemas directory when a matching schema exists. This keeps edits to the
content honest: a typo'd key or a missing required field is reported clearly
instead of silently producing a broken page.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from isaac_cf_wong.site.content import load_content


class ValidationError(Exception):
    """Raised when one or more content files fail schema validation."""


def _load_schema(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_content(content_dir: Path, schemas_dir: Path) -> list[str]:
    """Validate every content file that has a matching schema.

    Args:
        content_dir: Directory containing the content files.
        schemas_dir: Directory containing ``<name>.schema.json`` files.

    Returns:
        A list of human-readable error messages. Empty when everything is valid.

    """
    content = load_content(content_dir)
    errors: list[str] = []
    for name, document in content.items():
        schema_path = schemas_dir / f"{name}.schema.json"
        if not schema_path.exists():
            continue
        validator = Draft202012Validator(_load_schema(schema_path))
        for error in sorted(validator.iter_errors(document), key=str):
            location = "/".join(str(part) for part in error.absolute_path) or "(root)"
            errors.append(f"{name}.yaml: at '{location}': {error.message}")
    return errors


def validate_or_raise(content_dir: Path, schemas_dir: Path) -> None:
    """Validate content and raise :class:`ValidationError` if anything fails.

    Args:
        content_dir: Directory containing the content files.
        schemas_dir: Directory containing the schema files.

    Raises:
        ValidationError: If any content file fails validation.

    """
    errors = validate_content(content_dir, schemas_dir)
    if errors:
        raise ValidationError("\n".join(errors))
