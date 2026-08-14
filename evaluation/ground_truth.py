"""
evaluation/ground_truth.py
--------------------------
Loads and validates the manually annotated ground-truth dataset.

Format
------
Ground truth is stored as a list of dicts in a JSON file (ground_truth.json).
Each entry represents one annotated PII occurrence:

    {
        "text":             "Sarthak Malvadkar",
        "normalized_label": "PERSON",
        "block_id":         "para_12",   // optional — used for strict matching
        "start":            0,           // optional — character offset
        "end":              18           // optional — character offset
    }

Two matching modes
------------------
* text_match  (default): an entity is a TP if its (text, label) pair
  appears in the ground truth, regardless of exact position.  Robust to
  minor block-ID changes between runs.
* span_match: strict — requires (block_id, start, end, label) to match.
  Use this for reproducibility audits.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GroundTruthEntry:
    text:             str
    normalized_label: str
    block_id:         Optional[str] = None
    start:            Optional[int] = None
    end:              Optional[int] = None


class GroundTruth:

    def __init__(self, entries: List[GroundTruthEntry]) -> None:
        self.entries = entries

    @staticmethod
    def _normalized_label(entry: dict) -> str:
        label = entry.get("normalized_label")
        if label is None:
            label = entry.get("label")
        if label is None:
            raise KeyError("Ground-truth entry must include either 'normalized_label' or 'label'")
        return label

    @classmethod
    def from_file(cls, path: str) -> "GroundTruth":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = [
            GroundTruthEntry(
                text=d["text"],
                normalized_label=cls._normalized_label(d),
                block_id=d.get("block_id"),
                start=d.get("start"),
                end=d.get("end"),
            )
            for d in data
        ]
        logger.info("GroundTruth: loaded %d entries from '%s'", len(entries), path)
        return cls(entries)

    @classmethod
    def from_list(cls, raw: list) -> "GroundTruth":
        """Convenience constructor for inline ground truth (tests, notebooks)."""
        entries = [
            GroundTruthEntry(
                text=d["text"],
                normalized_label=cls._normalized_label(d),
                block_id=d.get("block_id"),
                start=d.get("start"),
                end=d.get("end"),
            )
            for d in raw
        ]
        return cls(entries)

    def by_label(self, label: str) -> List[GroundTruthEntry]:
        return [e for e in self.entries if e.normalized_label == label]

    def all_labels(self) -> List[str]:
        return sorted({e.normalized_label for e in self.entries})

    def as_text_set(self, label: Optional[str] = None) -> set[tuple[str, str]]:
        """Return {(text.lower(), label)} for text-based matching."""
        entries = self.entries if label is None else self.by_label(label)
        return {(e.text.strip().lower(), e.normalized_label) for e in entries}
