"""
pipeline/policy.py
------------------
Converts reconciled, context-enriched entities into redaction decisions.

Decisions
---------
  REDACT  — replace the entity text with a fake alternative
  KEEP    — leave the text unchanged
  REVIEW  — flag for manual review (logged but not redacted by default)

Policy rules (applied in order)
--------------------------------
1. If normalized_label is in REDACT_LABELS -> REDACT
2. If normalized_label is in KEEP_LABELS   -> KEEP
3. If agreement=False AND detection_confidence < REVIEW_THRESHOLD -> REVIEW
4. Anything else (unknown label, high-confidence single detector)   -> REVIEW

The policy is intentionally conservative: when in doubt, REVIEW rather
than REDACT (avoids over-redaction) or KEEP (avoids missing real PII).
"""

from __future__ import annotations

import logging
from typing import List

from config import DETECTION_THRESHOLD, KEEP_LABELS, REDACT_LABELS, REVIEW_THRESHOLD
from entity import Entity

logger = logging.getLogger(__name__)


class Policy:

    def apply(self, entities: List[Entity]) -> List[Entity]:
        """
        Stamps each entity with a `redaction_decision` and returns the list.
        """
        for ent in entities:
            ent.redaction_decision = self._decide(ent)
            if ent.redaction_decision == "REVIEW":
                logger.debug(
                    "REVIEW entity: %r  label=%s  conf=%.2f  agreement=%s",
                    ent.text, ent.normalized_label,
                    ent.detection_confidence, ent.agreement,
                )
        return entities

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _decide(self, ent: Entity) -> str:
        label = ent.normalized_label
        conf  = ent.detection_confidence

        # Hard rules first
        if label in REDACT_LABELS:
            # Even for REDACT labels, require minimum confidence unless
            # the entity came from the deterministic regex layer (conf == 1.0).
            if conf >= DETECTION_THRESHOLD:
                return "REDACT"
            return "REVIEW"

        if label in KEEP_LABELS:
            return "KEEP"

        # Unknown label — review if confidence is insufficient, else REDACT
        if not ent.agreement and conf < REVIEW_THRESHOLD:
            return "REVIEW"

        # High-confidence, agreed-upon entity with an unmapped label
        return "REVIEW"
