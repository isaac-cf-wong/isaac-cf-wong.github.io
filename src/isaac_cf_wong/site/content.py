"""Loading of the structured YAML content files.

Each ``*.yaml`` file in the content directory becomes one top-level entry in
the returned mapping, keyed by its filename stem (e.g. ``profile.yaml`` ->
``"profile"``). This is the single source of truth that the templates render.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> Any:
    """Parse a single YAML file and return its contents.

    Args:
        path: Path to the YAML file.

    Returns:
        The parsed document (typically a mapping).

    """
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_content(content_dir: Path) -> dict[str, Any]:
    """Load every ``*.yaml`` file in ``content_dir`` keyed by filename stem.

    Args:
        content_dir: Directory containing the content files.

    Returns:
        Mapping from filename stem to parsed document.

    Raises:
        FileNotFoundError: If the content directory does not exist.

    """
    if not content_dir.is_dir():
        raise FileNotFoundError(f"Content directory not found: {content_dir}")
    content: dict[str, Any] = {}
    for path in sorted(content_dir.glob("*.yaml")):
        content[path.stem] = load_yaml(path)
    return content
