"""
detectors/ettin_detector.py
---------------------------
Ettin-Nemotron-PII wrapper with high-speed batched torch.no_grad() inference.
"""

from __future__ import annotations

import logging
import os
import re
from typing import List

import torch
torch.set_num_threads(max(1, os.cpu_count() or 4))

from tqdm import tqdm

from config import DETECTION_THRESHOLD, LABEL_MAP
from detectors.base import BaseDetector
from entity import Entity

logger = logging.getLogger(__name__)


def _is_pii_candidate(text: str) -> bool:
    t = text.strip()
    return len(t) >= 10 and bool(re.search(r'[A-Z0-9@]', t))


class EttinDetector(BaseDetector):

    def __init__(self) -> None:
        from transformers import pipeline
        self.ner = pipeline(
            "ner",
            model="kalyan-ks/ettin-68m-nemotron-pii",
            aggregation_strategy="simple",
        )

    def detect(self, text: str, block_id: str) -> List[Entity]:
        if not text or not _is_pii_candidate(text):
            return []

        try:
            with torch.no_grad():
                raw_entities = self.ner(text)
        except Exception:
            return []

        merged = self._merge(raw_entities, text)
        entities = []

        for ent in merged:
            raw_label = ent["entity_group"] if "entity_group" in ent else ent.get("label", "")
            normalized = LABEL_MAP.get(raw_label)
            if normalized is None:
                continue

            score = round(float(ent["score"]), 4)
            if score < DETECTION_THRESHOLD:
                continue

            entity = Entity(
                block_id=block_id,
                start=ent["start"],
                end=ent["end"],
                text=ent["word"] if "word" in ent else ent.get("text", ""),
                normalized_label=normalized,
                sources=["ettin"],
                raw_labels={"ettin": {"label": raw_label, "score": score}},
                detection_confidence=score,
                context_confidence=0.5,
                agreement=False,
            )
            entities.append(entity)

        return entities

    def detect_batch(self, blocks: list) -> List[Entity]:
        candidate_blocks = [b for b in blocks if b.text and _is_pii_candidate(b.text)]
        if not candidate_blocks:
            return []

        all_entities: List[Entity] = []

        with tqdm(total=len(candidate_blocks), desc="Ettin Detection ", unit="block") as pbar:
            for blk in candidate_blocks:
                try:
                    with torch.no_grad():
                        raw_entities = self.ner(blk.text)
                    merged = self._merge(raw_entities, blk.text)
                    for ent in merged:
                        raw_label = ent["entity_group"] if "entity_group" in ent else ent.get("label", "")
                        normalized = LABEL_MAP.get(raw_label)
                        if normalized is None:
                            continue
                        score = round(float(ent["score"]), 4)
                        if score < DETECTION_THRESHOLD:
                            continue
                        all_entities.append(
                            Entity(
                                block_id=blk.block_id,
                                start=ent["start"],
                                end=ent["end"],
                                text=ent["word"] if "word" in ent else ent.get("text", ""),
                                normalized_label=normalized,
                                sources=["ettin"],
                                raw_labels={"ettin": {"label": raw_label, "score": score}},
                                detection_confidence=score,
                                context_confidence=0.5,
                                agreement=False,
                            )
                        )
                except Exception as exc:
                    logger.debug("EttinDetector error: %s", exc)
                pbar.update(1)

        return all_entities

    def _merge(self, raw_entities: list, original_text: str) -> list:
        if not raw_entities:
            return []

        raw_entities = sorted(raw_entities, key=lambda x: x["start"])
        merged = []
        first_group = raw_entities[0].get("entity_group", raw_entities[0].get("label", ""))
        first_word = raw_entities[0].get("word", raw_entities[0].get("text", ""))

        current = {
            "start": raw_entities[0]["start"],
            "end":   raw_entities[0]["end"],
            "entity_group": first_group,
            "score": raw_entities[0]["score"],
            "word":  first_word,
        }

        for nxt in raw_entities[1:]:
            group = nxt.get("entity_group", nxt.get("label", ""))
            same_label  = group == current["entity_group"]
            is_adjacent = nxt["start"] <= current["end"] + 1

            if same_label and is_adjacent:
                current["end"]   = max(current["end"], nxt["end"])
                current["score"] = max(current["score"], nxt["score"])
                current["word"]  = original_text[current["start"]:current["end"]]
            else:
                merged.append(current)
                current = {
                    "start": nxt["start"],
                    "end":   nxt["end"],
                    "entity_group": group,
                    "score": nxt["score"],
                    "word":  nxt.get("word", nxt.get("text", "")),
                }

        merged.append(current)
        return merged