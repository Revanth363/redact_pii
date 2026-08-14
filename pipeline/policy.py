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
1. If text is in GENERIC_EXCLUSIONS (e.g. generic words "Company", "Board", "Issuer") -> KEEP
2. If normalized_label is in REDACT_LABELS -> REDACT
3. If normalized_label is in KEEP_LABELS   -> KEEP
4. Anything else                           -> REVIEW
"""

from __future__ import annotations

import logging
from typing import List

from config import DETECTION_THRESHOLD, KEEP_LABELS, REDACT_LABELS, REVIEW_THRESHOLD
from entity import Entity

logger = logging.getLogger(__name__)

# Common generic legal/document vocabulary terms that AI models often flag as PII,
# but which are generic non-PII terms in a Red Herring Prospectus.
GENERIC_EXCLUSIONS = {
    "company",
    "our company",
    "the company",
    "board",
    "board of directors",
    "directors",
    "issuer",
    "offer",
    "registrar",
    "maharashtra",
    "india",
    "pune",
    "mumbai",
    "equity shares",
    "red herring prospectus",
    "shareholders",
    "promoter selling shareholders",
    "bhabha",
    "regional director",
    "managing director",
    "executive director",
}


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
        text_lower = ent.text.strip().lower()

        # 1. Filter out generic dictionary words
        if text_lower in GENERIC_EXCLUSIONS:
            return "KEEP"

        label = ent.normalized_label
        conf  = ent.detection_confidence

        # 2. Hard rules for REDACT labels
        if label in REDACT_LABELS:
            if conf >= DETECTION_THRESHOLD or ent.sources == ["regex"]:
                return "REDACT"
            return "REVIEW"

        # 3. Hard rules for KEEP labels
        if label in KEEP_LABELS:
            return "KEEP"

        # 4. Unknown or low-confidence single detector
        if not ent.agreement and conf < REVIEW_THRESHOLD:
            return "REVIEW"

        return "REVIEW"
