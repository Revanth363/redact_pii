import re
from typing import List
from entity import Entity
from detectors.base import BaseDetector
from config import DOB_CONTEXT_KEYWORDS


def luhn_check(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10 == 0


class RegexDetector(BaseDetector):

    PATTERNS = {
        # Require @ sign with at least one dot in domain; local part must
        # not be immediately preceded by a slash (avoids matching URLs).
        "EMAIL": [
            r"(?<![/])\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
        ],
        "PHONE": [
            # +91 followed by optional separator then 10 digits (mobile)
            r"\+91[\s\-]?[6-9]\d{9}",
            # +91 <STD 2-5 digits> <subscriber 4-8 digits> with spaces/dashes
            r"\+91[\s\-]?\d{2,5}[\s\-]?\d{4,8}",
            # Landline: +91 <city 2-3 d> <space> <8 d> e.g. +91 20 45053237
            r"\+91\s\d{2,3}\s\d{4,5}\s?\d{4}",
            # Bare +91 dash format e.g. +91-20-26234000
            r"\+91-\d{2,5}-\d{4,8}",
            # Space between + and 91: '+ 91 20 45053237' or '+ 91 8879770456'
            # Require total >= 8 subscriber digits to avoid partial matches
            r"\+\s91\s(?:\d{2}\s\d{4}\s?\d{4}|\d{5}\s\d{5}|\d{10}|\d{2,5}[\s\-]?\d{7,8})",
        ],
        "IP": [
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ],
        "SSN": [
            r"\b\d{3}-\d{2}-\d{4}\b"
        ],
        # Require the number to stand alone (word boundaries) and be at
        # least 15 digits to avoid matching financial figures like 7,100.00
        "CREDIT_CARD": [
            r"(?<![\d,])\b(?:\d[ \-]?){15,19}\b(?![\d,])"
        ],
        "DOB": [
            r"\b(\d{1,2}[\s\-/]\w+[\s\-/]\d{2,4})\b",
            r"\b(\d{4}-\d{2}-\d{2})\b",
            r"\b(\d{2}/\d{2}/\d{4})\b",
        ],
    }

    def detect(self, text: str, block_id: str) -> List[Entity]:
        entities = []
        text_lower = text.lower()

        for label, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    matched_text = match.group().strip()

                    if label == "CREDIT_CARD":
                        digits_only = re.sub(r"[\s\-]", "", matched_text)
                        if len(digits_only) < 13 or len(digits_only) > 19:
                            continue
                        if not luhn_check(digits_only):
                            continue

                    if label == "IP":
                        parts = matched_text.split(".")
                        if not all(0 <= int(p) <= 255 for p in parts):
                            continue

                    if label == "DOB":
                        window_start = max(0, match.start() - 50)
                        window = text_lower[window_start:match.start()]
                        if not any(kw in window for kw in DOB_CONTEXT_KEYWORDS):
                            continue

                    entity = Entity(
                        block_id=block_id,
                        start=match.start(),
                        end=match.end(),
                        text=matched_text,
                        normalized_label=label,
                        sources=["regex"],
                        raw_labels={"regex": {"label": label, "score": 1.0}},
                        detection_confidence=1.0,
                        context_confidence=0.5,
                        agreement=True,
                    )
                    entities.append(entity)

        return entities