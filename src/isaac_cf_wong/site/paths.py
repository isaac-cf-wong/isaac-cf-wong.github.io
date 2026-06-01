"""Locations of the inputs and outputs used to build the site.

All paths are resolved relative to a project root (by default the current
working directory). Override individual directories only if you restructure
the repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SitePaths:
    """Resolved filesystem locations for a site build."""

    root: Path = field(default_factory=Path.cwd)
    content_dir: str = "content"
    schemas_dir: str = "schemas"
    templates_dir: str = "templates"
    assets_dir: str = "assets"
    output_dir: str = "_site"

    @property
    def content(self) -> Path:
        """Directory holding the structured YAML content files."""
        return self.root / self.content_dir

    @property
    def schemas(self) -> Path:
        """Directory holding the JSON Schema files used for validation."""
        return self.root / self.schemas_dir

    @property
    def templates(self) -> Path:
        """Directory holding the Jinja2 templates."""
        return self.root / self.templates_dir

    @property
    def assets(self) -> Path:
        """Directory holding static assets (CSS, JS, images, files)."""
        return self.root / self.assets_dir

    @property
    def output(self) -> Path:
        """Directory the rendered site is written to."""
        return self.root / self.output_dir
