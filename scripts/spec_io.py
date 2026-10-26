"""Load an mcp-spec file (YAML or JSON) and shared reference data."""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REFERENCE_DIR = os.path.join(HERE, "..", "reference")


def load_spec(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if path.endswith(".json"):
        return json.loads(text)
    try:
        import yaml  # type: ignore
    except ImportError:
        sys.exit("PyYAML is required for YAML specs: pip install pyyaml (or pass a .json spec)")
    return yaml.safe_load(text) or {}


def load_reference(name: str) -> dict:
    with open(os.path.join(REFERENCE_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)
