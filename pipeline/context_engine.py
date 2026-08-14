"""
pipeline/context_engine.py
--------------------------
Examines the text surrounding each detected entity and updates
`context_confidence` based on supporting keywords.

Responsibilities
----------------
* DOB disambiguation: a date is only promoted to DOB if nearby text
  contains DOB-context keywords (e.g. "date of birth", "born on").
* ADDRESS boosting: a detected address span gets higher context_confidence
  when adjacent text contains address-context keywords.
* PERSON boosting: names adjacent to role keywords (director, promoter…)
  get higher context_confidence.
* COMPANY boosting: organisation names near legal-suffix keywords.

The context engine does NOT make the final redaction decision — that is
the Policy layer's job.  It only sets `context_confidence` and may
change `normalized_label` when disambiguation is unambiguous (e.g.
downgrading DOB to DATE when no DOB keyword is found within the window).

The text of the full block is passed in so we can read the context window
around each entity span.
"""

from __future__ import annotations

import re
from typing import List

from config import (
    ADDRESS_CONTEXT_KEYWORDS,
    COMPANY_CONTEXT_KEYWORDS,
    DOB_CONTEXT_KEYWORDS,
    PERSON_CONTEXT_KEYWORDS,
)
from entity import Entity

_WINDOW = 80   # characters of context to inspect on each side of the span


class ContextEngine:

    def process(
        self,
        entities: List[Entity],
        block_texts: dict[str, str],
    ) -> List[Entity]:
        """
        Parameters
        ----------
        entities:
            Reconciled entity list (may span multiple blocks).
        block_texts:
            Mapping of block_id -> full text of that block.

        Returns
        -------
        The same list of Entity objects with updated context_confidence
        (and occasionally updated normalized_label).
        """
        for ent in entities:
            text = block_texts.get(ent.block_id, "")
            self._enrich(ent, text)
        return entities

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _enrich(self, ent: Entity, block_text: str) -> None:
        label = ent.normalized_label

        if label == "DOB":
            self._handle_dob(ent, block_text)
        elif label == "DATE":
            self._maybe_promote_to_dob(ent, block_text)
        elif label == "ADDRESS":
            self._boost(ent, block_text, ADDRESS_CONTEXT_KEYWORDS, boost=0.25)
        elif label == "PERSON":
            self._boost(ent, block_text, PERSON_CONTEXT_KEYWORDS, boost=0.20)
        elif label == "COMPANY":
            self._boost(ent, block_text, COMPANY_CONTEXT_KEYWORDS, boost=0.20)

    def _window(self, ent: Entity, block_text: str) -> str:
        """Return a lowercase context window around the entity span."""
        lo = max(0, ent.start - _WINDOW)
        hi = min(len(block_text), ent.end + _WINDOW)
        return block_text[lo:hi].lower()

    def _boost(
        self,
        ent: Entity,
        block_text: str,
        keywords: List[str],
        boost: float,
    ) -> None:
        window = self._window(ent, block_text)
        if any(kw in window for kw in keywords):
            ent.context_confidence = min(1.0, ent.context_confidence + boost)

    def _handle_dob(self, ent: Entity, block_text: str) -> None:
        """
        If the entity is already labelled DOB (by the model or regex),
        confirm it with a context check.  If no DOB keyword is found,
        downgrade it to DATE so the policy will KEEP it.
        """
        window = self._window(ent, block_text)
        if any(kw in window for kw in DOB_CONTEXT_KEYWORDS):
            ent.context_confidence = min(1.0, ent.context_confidence + 0.35)
        else:
            # No DOB context — this is probably just an ordinary date
            ent.normalized_label = "DATE"
            ent.context_confidence = 0.3

    def _maybe_promote_to_dob(self, ent: Entity, block_text: str) -> None:
        """
        A DATE-labelled entity near DOB keywords should be reclassified.
        """
        window = self._window(ent, block_text)
        if any(kw in window for kw in DOB_CONTEXT_KEYWORDS):
            ent.normalized_label = "DOB"
            ent.context_confidence = min(1.0, ent.context_confidence + 0.35)
