"""
evaluation/evaluator.py
-----------------------
Computes precision, recall, and F1 for each PII label by comparing
detected entities against the ground truth.

Matching
--------
Default mode: text_match
  An entity is a TP if (entity.text.lower(), entity.normalized_label)
  appears in the ground-truth set.  This is forgiving of minor span
  misalignments while still requiring the correct label.

The evaluator runs per-label AND per-experiment so we can compare:

    Experiment 1: regex only
    Experiment 2: regex + ettin
    Experiment 3: regex + gliner2
    Experiment 4: regex + ettin + gliner2

Usage
-----
    from evaluation.evaluator import Evaluator
    from evaluation.ground_truth import GroundTruth

    gt     = GroundTruth.from_file("ground_truth.json")
    result = Evaluator().evaluate(detected_entities, gt)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

from entity import Entity
from evaluation.ground_truth import GroundTruth


@dataclass
class LabelMetrics:
    label:     str
    tp:        int = 0
    fp:        int = 0
    fn:        int = 0
    precision: float = 0.0
    recall:    float = 0.0
    f1:        float = 0.0

    def compute(self) -> None:
        if self.tp + self.fp > 0:
            self.precision = self.tp / (self.tp + self.fp)
        if self.tp + self.fn > 0:
            self.recall = self.tp / (self.tp + self.fn)
        if self.precision + self.recall > 0:
            self.f1 = (
                2 * self.precision * self.recall
                / (self.precision + self.recall)
            )


@dataclass
class EvaluationResult:
    experiment_name: str
    per_label:       Dict[str, LabelMetrics] = field(default_factory=dict)
    overall:         LabelMetrics = field(
        default_factory=lambda: LabelMetrics(label="OVERALL")
    )


class Evaluator:

    def evaluate(
        self,
        detected: List[Entity],
        ground_truth: GroundTruth,
        experiment_name: str = "experiment",
        redact_only: bool = True,
    ) -> EvaluationResult:
        """
        Parameters
        ----------
        detected:
            All entities produced by the pipeline (after policy).
        ground_truth:
            The GroundTruth object to compare against.
        experiment_name:
            Label for this run (used in the report).
        redact_only:
            If True, only consider entities whose redaction_decision == REDACT.
            Set False to evaluate detection-only (before policy).
        """
        # Filter to REDACT decisions if requested
        if redact_only:
            detected = [e for e in detected if e.redaction_decision == "REDACT"]

        # Build a set of (text, label) from detected
        detected_set: set[tuple[str, str]] = {
            (e.text.strip().lower(), e.normalized_label) for e in detected
        }

        # Ground-truth set
        gt_set = ground_truth.as_text_set()

        # All labels that appear in either GT or detections
        all_labels = ground_truth.all_labels()
        detected_labels = {e.normalized_label for e in detected}
        all_labels = sorted(set(all_labels) | detected_labels)

        result = EvaluationResult(experiment_name=experiment_name)

        total_tp = total_fp = total_fn = 0

        for label in all_labels:
            gt_label_set = ground_truth.as_text_set(label)
            det_label_set = {
                (t, l) for (t, l) in detected_set if l == label
            }

            tp = len(gt_label_set & det_label_set)
            fp = len(det_label_set - gt_label_set)
            fn = len(gt_label_set - det_label_set)

            m = LabelMetrics(label=label, tp=tp, fp=fp, fn=fn)
            m.compute()
            result.per_label[label] = m

            total_tp += tp
            total_fp += fp
            total_fn += fn

        overall = LabelMetrics(
            label="OVERALL", tp=total_tp, fp=total_fp, fn=total_fn
        )
        overall.compute()
        result.overall = overall

        return result
