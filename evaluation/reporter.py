"""
evaluation/reporter.py
----------------------
Renders EvaluationResult objects as formatted tables.

Outputs
-------
* print_report()   -> pretty console table via tabulate (fallback: plain text)
* to_markdown()    -> GitHub-flavoured Markdown string
* to_dict()        -> plain dict (for JSON serialisation or further processing)
* compare_experiments() -> side-by-side comparison of multiple results
"""

from __future__ import annotations

from typing import List

from evaluation.evaluator import EvaluationResult, LabelMetrics

try:
    from tabulate import tabulate as _tabulate
    _tabulate_available = True
except ImportError:
    _tabulate_available = False


def _row(m: LabelMetrics) -> List:
    return [
        m.label,
        m.tp,
        m.fp,
        m.fn,
        f"{m.precision:.3f}",
        f"{m.recall:.3f}",
        f"{m.f1:.3f}",
    ]


_HEADERS = ["Label", "TP", "FP", "FN", "Precision", "Recall", "F1"]


class Reporter:

    def print_report(self, result: EvaluationResult) -> None:
        """Print a formatted table to stdout."""
        print(f"\n=== {result.experiment_name} ===")
        rows = [_row(m) for m in result.per_label.values()]
        rows.append(["-" * 12] + ["-" * 4] * 3 + ["-" * 9] * 3)
        rows.append(_row(result.overall))

        if _tabulate_available:
            print(_tabulate(rows, headers=_HEADERS, tablefmt="grid"))
        else:
            # Fallback plain text
            print("\t".join(_HEADERS))
            for row in rows:
                print("\t".join(str(c) for c in row))

    def to_markdown(self, result: EvaluationResult) -> str:
        """Return a GitHub-flavoured Markdown table string."""
        lines = [f"## {result.experiment_name}", ""]
        # Header
        lines.append("| " + " | ".join(_HEADERS) + " |")
        lines.append("| " + " | ".join(["---"] * len(_HEADERS)) + " |")
        for m in result.per_label.values():
            lines.append("| " + " | ".join(str(c) for c in _row(m)) + " |")
        lines.append("| " + " | ".join(["---"] * len(_HEADERS)) + " |")
        lines.append("| " + " | ".join(str(c) for c in _row(result.overall)) + " |")
        lines.append("")
        return "\n".join(lines)

    def compare_experiments(
        self,
        results: List[EvaluationResult],
        output_path: str = "evaluation_report.md",
    ) -> str:
        """
        Produce a combined Markdown report comparing multiple experiments.

        Returns the full Markdown string and optionally writes it to a file.
        """
        sections = ["# PII Redaction — Evaluation Report\n"]

        # Summary table: one row per experiment, overall F1
        sections.append("## Experiment Comparison (Overall)\n")
        summary_headers = ["Experiment", "Precision", "Recall", "F1"]
        summary_rows = [
            [
                r.experiment_name,
                f"{r.overall.precision:.3f}",
                f"{r.overall.recall:.3f}",
                f"{r.overall.f1:.3f}",
            ]
            for r in results
        ]
        sections.append("| " + " | ".join(summary_headers) + " |")
        sections.append("| " + " | ".join(["---"] * len(summary_headers)) + " |")
        for row in summary_rows:
            sections.append("| " + " | ".join(row) + " |")
        sections.append("")

        # Detailed per-experiment tables
        sections.append("---\n")
        sections.append("## Detailed Results\n")
        for r in results:
            sections.append(self.to_markdown(r))

        markdown = "\n".join(sections)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown)

        return markdown

    def to_dict(self, result: EvaluationResult) -> dict:
        return {
            "experiment": result.experiment_name,
            "per_label": {
                label: {
                    "tp": m.tp,
                    "fp": m.fp,
                    "fn": m.fn,
                    "precision": round(m.precision, 4),
                    "recall":    round(m.recall,    4),
                    "f1":        round(m.f1,         4),
                }
                for label, m in result.per_label.items()
            },
            "overall": {
                "tp": result.overall.tp,
                "fp": result.overall.fp,
                "fn": result.overall.fn,
                "precision": round(result.overall.precision, 4),
                "recall":    round(result.overall.recall,    4),
                "f1":        round(result.overall.f1,         4),
            },
        }
