"""Reference data for procedures, rules, and agencies."""

from pathlib import Path
from typing import Any

import json


def load_json(filename: str) -> Any:
    """Load JSON from the data directory."""
    file_path = Path(__file__).parent.joinpath(filename)
    with file_path.open() as f:
        return json.load(f)


PROCEDURES = load_json("procedures.json")
SCORING_RULES = load_json("scoring_rules.json")
REQUIRED_DOCS = load_json("required_docs_by_procedure.json")
AGENCIES = load_json("agencies.json")

__all__ = [
    "PROCEDURES",
    "SCORING_RULES",
    "REQUIRED_DOCS",
    "AGENCIES",
    "load_json",
]
