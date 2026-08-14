"""
detectors/gliner_detector.py
----------------------------
GLiNER-backed PII detector with chunking for long paragraphs and robust entity extraction across all text cases.
"""

from __future__ import annotations

import logging
import os
import re
from typing import List, Optional

import torch
torch.set_num_threads(max(1, os.cpu_count() or 4))

from tqdm import tqdm

from config import DETECTION_THRESHOLD, LABEL_MAP
from detectors.base import BaseDetector
from entity import Entity

logger = logging.getLogger(__name__)

GLINER_LABELS: List[str] = [
    "person",
    "organization",
    "email address",
    "phone number",
    "address",
    "date of birth",
]

_GLINER_MAP: dict[str, str] = {
    "person":                 "PERSON",
    "organization":           "COMPANY",
    "email address":          "EMAIL",
    "phone number":           "PHONE",
    "address":                "ADDRESS",
    "date of birth":          "DOB",
}
_EFFECTIVE_MAP: dict[str, str] = {**LABEL_MAP, **_GLINER_MAP}


def _is_pii_candidate(text: str) -> bool:
    t = text.strip()
    return len(t) >= 10 and bool(re.search(r'[A-Za-z0-9@]', t))


def _chunk_text(text: str, max_chars: int = 1000) -> List[tuple[int, str]]:
    """Split long text into overlapping chunks of max_chars with character offset tracking."""
    if len(text) <= max_chars:
        return [(0, text)]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append((start, text[start:end]))
        if end == len(text):
            break
        start += max_chars - 100
    return chunks


class GlinerDetector(BaseDetector):

    def __init__(
        self,
        model_name: str = "urchade/gliner_multi_pii-v1",
        threshold: float = DETECTION_THRESHOLD,
    ) -> None:
        try:
            from gliner import GLiNER
            self._model = GLiNER.from_pretrained(model_name)
            self._threshold = threshold
            logger.info("GlinerDetector: loaded '%s'", model_name)
        except ImportError as exc:
            raise ImportError("Install the gliner package: pip install gliner") from exc

    def detect(self, text: str, block_id: str) -> List[Entity]:
        if not text or not _is_pii_candidate(text):
            return []

        chunks = _chunk_text(text)
        entities: List[Entity] = []

        try:
            with torch.no_grad():
                for offset, chunk_str in chunks:
                    raw_entities = self._model.predict_entities(
                        chunk_str,
                        GLINER_LABELS,
                        threshold=self._threshold,
                    )
                    for raw in raw_entities:
                        ent = self._convert(raw, block_id, offset)
                        if ent is not None:
                            entities.append(ent)
        except Exception:
            return []

        return self._dedup(entities)

    def detect_batch(self, blocks: list, batch_size: int = 32) -> List[Entity]:
        candidate_blocks = [b for b in blocks if b.text and _is_pii_candidate(b.text)]
        if not candidate_blocks:
            return []

        all_entities: List[Entity] = []

        with tqdm(total=len(candidate_blocks), desc="GLiNER Detection", unit="block") as pbar:
            for blk in candidate_blocks:
                chunks = _chunk_text(blk.text)
                blk_ents = []
                try:
                    with torch.no_grad():
                        for offset, chunk_str in chunks:
                            raw_entities = self._model.predict_entities(
                                chunk_str,
                                GLINER_LABELS,
                                threshold=self._threshold,
                            )
                            for raw in raw_entities:
                                ent = self._convert(raw, blk.block_id, offset)
                                if ent is not None:
                                    blk_ents.append(ent)
                    all_entities.extend(self._dedup(blk_ents))
                except Exception as exc:
                    logger.debug("GlinerDetector error: %s", exc)
                pbar.update(1)

        return all_entities

    def _convert(self, raw: dict, block_id: str, offset: int = 0) -> Optional[Entity]:
        raw_label = raw.get("label", "").lower().strip()
        normalized = _EFFECTIVE_MAP.get(raw_label)
        if normalized is None:
            return None

        score = round(float(raw.get("score", 0.0)), 4)
        if score < self._threshold:
            return None

        start = raw.get("start", 0) + offset
        end = raw.get("end", 0) + offset
        span = raw.get("text", "").strip()

        return Entity(
            block_id=block_id,
            start=int(start),
            end=int(end),
            text=span,
            normalized_label=normalized,
            sources=["gliner2"],
            raw_labels={"gliner2": {"label": raw_label, "score": score}},
            detection_confidence=score,
            context_confidence=0.5,
            agreement=False,
        )

    @staticmethod
    def _dedup(entities: List[Entity]) -> List[Entity]:
        best: dict[tuple, Entity] = {}
        for ent in entities:
            key = (ent.block_id, ent.start, ent.normalized_label)
            if key not in best or ent.detection_confidence > best[key].detection_confidence:
                best[key] = ent
        return sorted(best.values(), key=lambda e: e.start)
