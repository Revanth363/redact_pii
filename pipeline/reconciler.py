"""
pipeline/reconciler.py
----------------------
Merges entity lists from multiple detectors into a single deduplicated
list of Entity objects.

Rules
-----
1. Two entities are considered the *same* if their text blocks overlap
   (start < other.end AND end > other.start) AND they carry the same
   normalized_label.
2. When entities overlap:
   - Their `sources` lists are merged.
   - `agreement` is set True if two or more different sources found the span.
   - `detection_confidence` is set to the max score across all sources.
   - `raw_labels` dicts are merged so downstream code can inspect per-source scores.
3. Entities that don't overlap with anything else are passed through
   unchanged (agreement stays False, sources keeps its single-item list).
4. Non-overlapping entities from different detectors with the *same* text
   but *different* labels are kept as separate entities — the policy layer
   resolves ambiguity.
"""

from __future__ import annotations

from typing import List
from entity import Entity


class Reconciler:

    def reconcile(self, *detector_outputs: List[Entity]) -> List[Entity]:
        """
        Parameters
        ----------
        *detector_outputs:
            One list of Entity objects per detector, in any order.

        Returns
        -------
        A single sorted, deduplicated list of Entity objects.
        """
        # Flatten all detector outputs into one list
        all_entities: List[Entity] = []
        for entity_list in detector_outputs:
            all_entities.extend(entity_list)

        if not all_entities:
            return []

        # Group by block_id so we only compare within the same text block
        from collections import defaultdict
        by_block: dict[str, List[Entity]] = defaultdict(list)
        for ent in all_entities:
            by_block[ent.block_id].append(ent)

        result: List[Entity] = []
        for block_id, block_entities in by_block.items():
            merged = self._merge_block(block_entities)
            result.extend(merged)

        return result

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _merge_block(self, entities: List[Entity]) -> List[Entity]:
        """Merge overlapping same-label entities within one block."""
        # Sort by start position
        entities = sorted(entities, key=lambda e: e.start)

        merged: List[Entity] = []
        used = [False] * len(entities)

        for i, base in enumerate(entities):
            if used[i]:
                continue

            # Collect all entities that overlap base AND share its label
            cluster: List[Entity] = [base]
            for j, other in enumerate(entities):
                if j <= i or used[j]:
                    continue
                if other.normalized_label != base.normalized_label:
                    continue
                if self._overlaps(base, other):
                    cluster.append(other)
                    used[j] = True

            used[i] = True
            merged.append(self._fuse(cluster))

        return sorted(merged, key=lambda e: e.start)

    @staticmethod
    def _overlaps(a: Entity, b: Entity) -> bool:
        return a.start < b.end and a.end > b.start

    @staticmethod
    def _fuse(cluster: List[Entity]) -> Entity:
        """Combine a cluster of overlapping same-label entities into one."""
        if len(cluster) == 1:
            return cluster[0]

        # Take the span with the widest coverage as the canonical span
        best = max(cluster, key=lambda e: e.detection_confidence)

        all_sources: List[str] = []
        merged_raw: dict = {}
        for ent in cluster:
            for src in ent.sources:
                if src not in all_sources:
                    all_sources.append(src)
            merged_raw.update(ent.raw_labels)

        # Use the longest text span
        canon_text = max((e.text for e in cluster), key=len)
        start = min(e.start for e in cluster)
        end   = max(e.end   for e in cluster)

        fused = Entity(
            block_id=best.block_id,
            start=start,
            end=end,
            text=canon_text,
            normalized_label=best.normalized_label,
            sources=all_sources,
            raw_labels=merged_raw,
            detection_confidence=max(e.detection_confidence for e in cluster),
            context_confidence=max(e.context_confidence for e in cluster),
            agreement=len(set(all_sources)) >= 2,
        )
        return fused
