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


def looks_like_person_name(text: str) -> bool:
    """A lightweight sanity check for obvious personal-name spans."""
    words = [w.strip() for w in text.strip().split() if w.strip()]
    if len(words) < 2 or len(words) > 5:
        return False

    cleaned = []
    for word in words:
        if not word:
            continue
        if word[0].isalpha() and not word[0].isupper():
            return False
        cleaned.append(word)

    if len(cleaned) < 2:
        return False

    return all(word and word[0].isalpha() and word[0].isupper() for word in cleaned)


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
    "we",
    "our",
    "us",
    "you",
    "they",
    "them",
    "customers",
    "our customers",
    "our business",
    "business",
    "bidder",
    "anchor investor",
    "anchor investors",
    "investor",
    "investors",
    "shareholder",
    "shareholders",
    "promoter",
    "promoters",
    "registered office",
    "registered offices",
    "sponsor banks",
    "banks",
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
        conf = ent.detection_confidence

        # 2. Hard rules for KEEP labels
        if label in KEEP_LABELS:
            return "KEEP"

        # 3. Strong automatic redaction for regex-backed high-confidence identifiers
        if label in {"EMAIL", "PHONE"}:
            if conf >= DETECTION_THRESHOLD or ent.sources == ["regex"]:
                return "REDACT"
            return "REVIEW"

        # 4. Semantic labels need stronger evidence before redaction.
        if label in {"PERSON", "COMPANY", "ADDRESS"}:

            # Multiple independent detectors agreeing is strong evidence.
            if ent.agreement:
                return "REDACT"

            # PERSON: require a plausible multi-word name and reasonably high confidence.
            if label == "PERSON":
                if looks_like_person_name(ent.text) and conf >= 0.80:
                    return "REDACT"
                return "REVIEW"

            # COMPANY: company names often have strong corporate suffixes.
            if label == "COMPANY":
                company_indicators = (
                    "limited",
                    "private limited",
                    "llp",
                    "ltd",
                    "inc.",
                    "incorporated",
                    "corporation",
                    "bank",
                    "securities",
                    "industries",
                    "infrastructure",
                    "logistics",
                    "services",
                    "management",
                )

                if conf >= 0.80 and any(x in text_lower for x in company_indicators):
                    return "REDACT"

                return "REVIEW"

            # ADDRESS: addresses usually contain structural/location indicators.
            if label == "ADDRESS":
                address_indicators = (
                    "plot",
                    "road",
                    "street",
                    "marg",
                    "village",
                    "taluka",
                    "floor",
                    "building",
                    "wing",
                    "tower",
                    "industrial area",
                    "complex",
                    "pune",
                    "mumbai",
                    "maharashtra",
                    "india",
                )

                if conf >= 0.75 and any(x in text_lower for x in address_indicators):
                    return "REDACT"

                return "REVIEW"

        # 5. Other REDACT labels retain the usual thresholding.
        if label in REDACT_LABELS:
            if conf >= DETECTION_THRESHOLD or ent.sources == ["regex"]:
                return "REDACT"
            return "REVIEW"

        # 6. Unknown or low-confidence single detector
        if not ent.agreement and conf < REVIEW_THRESHOLD:
            return "REVIEW"

        return "REVIEW"
