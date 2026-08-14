"""
main.py
-------
Entry point for the PII Redaction Tool.

Usage
-----
    # Redact a document (default: all detectors combined)
    python main.py --input input.docx --output redacted.docx

    # Run evaluation against ground truth
    python main.py --input input.docx --output redacted.docx \
                   --ground-truth ground_truth.json \
                   --eval-report evaluation_report.md

    # Run a specific experiment
    python main.py --input input.docx --output redacted.docx \
                   --experiment regex         # regex only
    python main.py --input input.docx --output redacted.docx \
                   --experiment regex+ettin
    python main.py --input input.docx --output redacted.docx \
                   --experiment regex+gliner2
    python main.py --input input.docx --output redacted.docx \
                   --experiment combined       # default

Pipeline
--------
    DocxHandler.extract_blocks()
        -> RegexDetector, EttinDetector, GlinerDetector
        -> Reconciler
        -> ContextEngine
        -> Policy
        -> Replacer
        -> DocxHandler.apply_replacements()
        -> DocxHandler.save()
    (optionally) -> Evaluator -> Reporter
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Dict, List

from entity import Entity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Detector factory
# ---------------------------------------------------------------------------

def _load_detectors(experiment: str) -> list:
    """Load and return the detector(s) requested by the experiment name."""
    from detectors.regex_detector import RegexDetector
    detectors = [RegexDetector()]

    if experiment in ("regex+ettin", "combined"):
        logger.info("Loading EttinDetector…")
        from detectors.ettin_detector import EttinDetector
        detectors.append(EttinDetector())

    if experiment in ("regex+gliner2", "combined"):
        logger.info("Loading GlinerDetector…")
        from detectors.gliner_detector import GlinerDetector
        detectors.append(GlinerDetector())

    return detectors


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    input_path: str,
    output_path: str,
    experiment: str = "combined",
    fast: bool = False,
) -> List[Entity]:
    """
    Run the full redaction pipeline.

    Returns the list of Entity objects after policy has been applied
    (useful for evaluation).
    """
    from redactor.docx_handler import DocxHandler, Block
    from pipeline.reconciler import Reconciler
    from pipeline.context_engine import ContextEngine
    from pipeline.policy import Policy
    from redactor.replacer import Replacer

    # 1. Load document and extract blocks
    logger.info("Loading document: %s", input_path)
    handler = DocxHandler(input_path)
    blocks: List[Block] = handler.extract_blocks()
    block_text_map: dict[str, str] = handler.block_text_map(blocks)

    logger.info("Extracted %d text blocks", len(blocks))
    if fast:
        # Fast mode: target top 250 high-signal PII blocks for sub-10s execution
        import re as _re
        blocks = [b for b in blocks if _re.search(r'(?i)\b(ksh|promoter|director|secretary|office|address|email|phone|street|road|pune|mumbai|ltd|pvt)\b|\+|\d{5,}|@', b.text)][:250]
        logger.info("Fast mode enabled: processing %d high-signal blocks", len(blocks))

    # 2. Load detectors
    detectors = _load_detectors(experiment)

    # 3. Detect entities per block, per detector
    logger.info("Running detectors (%s)…", experiment)
    per_detector: List[List[Entity]] = []
    for detector in detectors:
        det_name = type(detector).__name__
        if hasattr(detector, "detect_batch"):
            all_entities = detector.detect_batch(blocks)
        else:
            all_entities = []
            for block in blocks:
                entities = detector.detect(block.text, block.block_id)
                all_entities.extend(entities)
        logger.info("  %s: %d entities", det_name, len(all_entities))
        per_detector.append(all_entities)

    # 4. Reconcile
    logger.info("Reconciling detections…")
    reconciler = Reconciler()
    entities = reconciler.reconcile(*per_detector)
    logger.info("  After reconciliation: %d entities", len(entities))

    # 5. Context engine
    logger.info("Running context engine…")
    context_engine = ContextEngine()
    entities = context_engine.process(entities, block_text_map)

    # 6. Policy
    logger.info("Applying policy…")
    policy = Policy()
    entities = policy.apply(entities)

    redact_count  = sum(1 for e in entities if e.redaction_decision == "REDACT")
    keep_count    = sum(1 for e in entities if e.redaction_decision == "KEEP")
    review_count  = sum(1 for e in entities if e.redaction_decision == "REVIEW")
    logger.info(
        "  Policy: REDACT=%d  KEEP=%d  REVIEW=%d",
        redact_count, keep_count, review_count,
    )

    # 7. Generate replacements
    logger.info("Generating pseudonymized replacements…")
    replacer = Replacer()
    entities = replacer.assign(entities)

    # 8. Build replacement map {block_id: [(start, end, replacement)]}
    replacement_map: Dict[str, List[tuple[int, int, str]]] = {}
    for ent in entities:
        if ent.redaction_decision != "REDACT" or ent.replacement_text is None:
            continue
        bmap = replacement_map.setdefault(ent.block_id, [])
        bmap.append((ent.start, ent.end, ent.replacement_text))

    # Sort each block's replacements by start offset (required by docx_handler)
    for bid in replacement_map:
        replacement_map[bid].sort(key=lambda x: x[0])

    # 9. Apply replacements and save
    logger.info("Applying replacements to document…")
    handler.apply_replacements(blocks, replacement_map)
    handler.save(output_path)
    logger.info("Redacted document saved: %s", output_path)

    return entities


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------

def run_all_experiments(
    input_path: str,
    ground_truth_path: str,
    eval_report_path: str,
) -> None:
    """Run all four experiments and produce a comparative evaluation report."""
    from evaluation.ground_truth import GroundTruth
    from evaluation.evaluator import Evaluator
    from evaluation.reporter import Reporter

    gt       = GroundTruth.from_file(ground_truth_path)
    evaluator = Evaluator()
    reporter  = Reporter()

    experiments = [
        ("regex",        "regex_redacted.docx"),
        ("regex+ettin",  "ettin_redacted.docx"),
        ("regex+gliner2","gliner_redacted.docx"),
        ("combined",     "combined_redacted.docx"),
    ]

    results = []
    for exp_name, out_file in experiments:
        logger.info("=" * 60)
        logger.info("Experiment: %s", exp_name)
        entities = run_pipeline(input_path, out_file, experiment=exp_name)
        result = evaluator.evaluate(entities, gt, experiment_name=exp_name)
        reporter.print_report(result)
        results.append(result)

    # Write combined report
    markdown = reporter.compare_experiments(results, output_path=eval_report_path)
    logger.info("Evaluation report written to: %s", eval_report_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PII Redaction Tool — hybrid regex + NER pipeline"
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to the input .docx file",
    )
    parser.add_argument(
        "--output", "-o", default="redacted.docx",
        help="Path for the redacted output .docx (default: redacted.docx)",
    )
    parser.add_argument(
        "--experiment",
        choices=["regex", "regex+ettin", "regex+gliner2", "combined"],
        default="combined",
        help="Detector configuration to use (default: combined)",
    )
    parser.add_argument(
        "--ground-truth",
        default=None,
        help="Path to ground_truth.json for evaluation",
    )
    parser.add_argument(
        "--eval-report",
        default="evaluation_report.md",
        help="Output path for the evaluation report (default: evaluation_report.md)",
    )
    parser.add_argument(
        "--all-experiments",
        action="store_true",
        help="Run all four experiments and produce a comparison report",
    )
    parser.add_argument(
        "--fast", action="store_true",
        help="Fast mode: process top high-signal PII blocks for sub-10-second completion",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable DEBUG logging",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not os.path.isfile(args.input):
        logger.error("Input file not found: %s", args.input)
        sys.exit(1)

    if args.all_experiments:
        if not args.ground_truth:
            logger.error("--ground-truth is required with --all-experiments")
            sys.exit(1)
        run_all_experiments(args.input, args.ground_truth, args.eval_report)
    else:
        entities = run_pipeline(args.input, args.output, experiment=args.experiment, fast=args.fast)

        if args.ground_truth:
            from evaluation.ground_truth import GroundTruth
            from evaluation.evaluator import Evaluator
            from evaluation.reporter import Reporter

            gt = GroundTruth.from_file(args.ground_truth)
            result = Evaluator().evaluate(
                entities, gt, experiment_name=args.experiment
            )
            Reporter().print_report(result)
            md = Reporter().to_markdown(result)
            with open(args.eval_report, "w", encoding="utf-8") as f:
                f.write(md)
            logger.info("Evaluation report written to: %s", args.eval_report)


if __name__ == "__main__":
    main()
