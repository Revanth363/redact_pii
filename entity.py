from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Entity:
    block_id:          str
    start:             int
    end:               int
    text:              str
    normalized_label:  str

    sources:    list = field(default_factory=list)
    raw_labels: dict = field(default_factory=dict)

    detection_confidence: float = 0.0
    context_confidence:   float = 0.0
    agreement:            bool  = False

    redaction_decision: Optional[str] = None
    replacement_text:   Optional[str] = None

    def __repr__(self) -> str:
        return (
            f"Entity(text={self.text!r}, label={self.normalized_label}, "
            f"sources={self.sources}, det_conf={self.detection_confidence:.2f}, "
            f"ctx_conf={self.context_confidence:.2f}, agreement={self.agreement}, "
            f"decision={self.redaction_decision})"
        )

    def summary(self) -> dict:
        return {
            "block_id":             self.block_id,
            "text":                 self.text,
            "normalized_label":     self.normalized_label,
            "sources":              ", ".join(self.sources),
            "raw_labels":           self.raw_labels,
            "detection_confidence": round(self.detection_confidence, 4),
            "context_confidence":   round(self.context_confidence, 4),
            "agreement":            self.agreement,
            "redaction_decision":   self.redaction_decision,
            "replacement_text":     self.replacement_text,
        }