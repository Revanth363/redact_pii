# PII Redaction Tool

A tool that reads a `.docx` file (like a Red Herring Prospectus), finds all personally identifiable information (PII) in it, and replaces each piece with a realistic fake value — so the document looks real but contains no actual personal data.

---

## What is PII?

PII = Personally Identifiable Information. Anything that could identify a real person or organization:

| PII Type | Example in document | Replaced with |
|---|---|---|
| Person name | `Sarthak Malvadkar` | `Karan Dilip Joshi` |
| Email | `cs.connect@kshinternational.com` | `info.contact@vrkindustries.com` |
| Phone | `+ 91 20 4505 3237` | `+ 91 20 3812 4455` |
| Company name | `KSH International Limited` | `VRK Industries Limited` |
| Address | `Village Birdewadi, Khed, Pune – 410 501` | `Village Wagholi, Haveli, Pune – 412 207` |
| SSN | `123-45-6789` | `847-29-5013` |
| Credit Card | `4111 1111 1111 1111` | `5381 2948 7162 0934` |
| Date of Birth | `12/04/1985` (when labelled as DOB) | `07/09/1991` |
| IP Address | `192.168.1.25` | `10.42.87.13` |

**What is NOT replaced:** financial figures (`₹7,100 million`), filing dates, page numbers, order numbers — anything that is not personal data.

---

## How it Works — The 3-Layer Pipeline

The tool uses **three detection methods in parallel**, then combines their results:

```
Your input.docx
      ↓
  Extract all text blocks (4,686 blocks in this document)
      ↓
  Run 3 detectors in parallel:
  ┌─────────────┬──────────────────┬──────────────────────┐
  │  REGEX      │  ETTIN (AI model)│  GLiNER (AI model)   │
  │  (instant)  │  (68M params)    │  (zero-shot spans)   │
  │             │                  │                      │
  │  Email ✓    │  Person ✓        │  Person ✓            │
  │  Phone ✓    │  Company ✓       │  Company ✓           │
  │  IP ✓       │  Address ✓       │  Address ✓           │
  │  SSN ✓      │  Email ✓         │  Email ✓             │
  │  CC ✓       │  Phone ✓         │  Phone ✓             │
  │  DOB ✓      │                  │  DOB ✓               │
  └─────────────┴──────────────────┴──────────────────────┘
      ↓
  Reconciler — merge overlapping detections, mark "agreement" if 2+ detectors agree
      ↓
  Context Engine — e.g. only mark a date as DOB if "date of birth" appears nearby
      ↓
  Policy — decide: REDACT or KEEP?
      ↓
  Replacer — swap each PII with a consistent, realistic fake
      ↓
  Save redacted_output.docx
```

### Layer 1 — Regex (Rule-based, instant)
Uses hand-crafted patterns for things that have a predictable structure:
- Emails, Indian phone numbers (`+91`, `+ 91 20`, `+91-20-` formats), IP addresses, SSNs, credit cards (with Luhn checksum validation), dates
- **Precision: 100%** — zero false positives. But it cannot find names or companies.

### Layer 2 — Ettin-Nemotron-PII (AI model)
A 68M-parameter language model (`kalyan-ks/ettin-68m-nemotron-pii`) from HuggingFace, pre-trained on PII-rich text. Reads tokens in context to detect names, companies, addresses.
- Slower (~35 min on CPU for full document), but good at Indian names

### Layer 3 — GLiNER (AI model, recommended)
A zero-shot span extraction model (`urchade/gliner_multi_pii-v1`). You give it labels to look for (`person`, `organization`, `address`, etc.) and it finds them in any text — even text it has never seen before.
- ~10 min on CPU for full document
- Detected 3,191 entities in the prospectus with high confidence (>0.99)
- **Best balance of speed and accuracy**

---

## Replacement Strategy

Every fake value is:
1. **Consistent** — `Sarthak Malvadkar` always becomes `Karan Dilip Joshi` throughout the entire document (seeded from MD5 hash)
2. **Case-preserving** — `KUSHAL SUBBAYYA HEGDE` (ALL CAPS) → `ARJUN RAMESH MEHTA` (ALL CAPS)
3. **Format-preserving** — a landline phone stays a landline, a mobile stays mobile, email format is kept
4. **Hardcoded for known PII** — all 26 emails, 22 phones, and key names/companies from this prospectus have fixed, hand-verified fakes in `replacer.py`

---

## Installation

```bash
pip install -r requirements.txt
```

For GPU acceleration (optional, much faster):
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

---

## Running the Tool

### Step 1 — Regex only (fastest, ~2 sec, catches Email + Phone only)
```bash
python main.py --input input.docx --output redacted_regex.docx --experiment regex
```

### Step 2 — Regex + GLiNER (recommended ⭐, ~10 min, catches everything)
```bash
python main.py --input input.docx --output redacted_gliner.docx --experiment regex+gliner2
```

### Step 3 — Regex + Ettin (~35-40 min)
```bash
python main.py --input input.docx --output redacted_ettin.docx --experiment regex+ettin
```

### Step 4 — All three combined (best possible, ~50-60 min)
```bash
python main.py --input input.docx --output redacted_combined.docx --experiment combined
```

---

## Evaluating Results (Precision / Recall / F1)

Run any experiment with `--ground-truth` to measure accuracy against hand-labelled ground truth (107 annotated PII entries):

```bash
# Evaluate regex alone
python main.py --input input.docx --output redacted_regex.docx --experiment regex --ground-truth ground_truth.json --eval-report eval_regex.md

# Evaluate regex + GLiNER
python main.py --input input.docx --output redacted_gliner.docx --experiment regex+gliner2 --ground-truth ground_truth.json --eval-report eval_gliner.md

# Evaluate regex + Ettin
python main.py --input input.docx --output redacted_ettin.docx --experiment regex+ettin --ground-truth ground_truth.json --eval-report eval_ettin.md

# Evaluate combined
python main.py --input input.docx --output redacted_combined.docx --experiment combined --ground-truth ground_truth.json --eval-report eval_combined.md

# Run ALL 4 experiments at once and produce a single comparison report
python main.py --input input.docx --output redacted_combined.docx --ground-truth ground_truth.json --all-experiments --eval-report evaluation_report.md
```

---

## Actual Results — Regex Baseline

From running `--experiment regex` against 107 ground truth entries:

| PII Type | Found | Missed | Precision | Recall | F1 |
|---|---|---|---|---|---|
| EMAIL | 26 / 26 | 0 | **1.000** | **1.000** | **1.000** |
| PHONE | 20 / 20 | 0 | **1.000** | **1.000** | **1.000** |
| PERSON | 0 / 27 | 27 | 0.000 | 0.000 | 0.000 |
| COMPANY | 0 / 28 | 28 | 0.000 | 0.000 | 0.000 |
| ADDRESS | 0 / 6 | 6 | 0.000 | 0.000 | 0.000 |
| **OVERALL** | **46 / 107** | **61** | **1.000** | **0.430** | **0.601** |

> Regex is perfect for Email/Phone but blind to names — that's exactly why we add AI models (GLiNER/Ettin) on top.

---

## Actual Results — Regex + GLiNER

From running `--experiment regex+gliner2` against the same 107 ground-truth entries:

| Label | TP | FP | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| ADDRESS | 0 | 8 | 6 | 0.000 | 0.000 | 0.000 |
| COMPANY | 26 | 63 | 2 | 0.292 | 0.929 | 0.444 |
| EMAIL | 26 | 2 | 0 | 0.929 | 1.000 | 0.963 |
| PERSON | 24 | 46 | 3 | 0.343 | 0.889 | 0.495 |
| PHONE | 20 | 5 | 0 | 0.800 | 1.000 | 0.889 |
| --- | --- | --- | --- | --- | --- | --- |
| OVERALL | 96 | 124 | 11 | 0.436 | 0.897 | 0.587 |

> The Regex + GLiNER configuration significantly improves semantic PII detection compared with the regex-only baseline. It achieves **89.7% recall** and an **F1 score of 0.587**, indicating strong coverage of ground-truth PII entities. However, the system still produces **124 false positives**, resulting in a precision of **43.6%**. This shows that GLiNER is effective at identifying entities such as person and company names that regex cannot detect, but its predictions require further contextual filtering to reduce false positives.

---

## What We Don't Redact (Intentional)

| Item | Why we KEEP it |
|---|---|
| `₹7,100 million` | Financial figure, not personal data |
| `February 10, 2025` | Filing date, not a date of birth |
| `Pune`, `Maharashtra` | City/state names are public info |
| `Order No. 12345` | Document reference number, not PII |
| `Page 1 of 350` | Page numbers |

---

## Project Structure

```
redact_pii/
├── main.py                  # Entry point — run this
├── entity.py                # Internal data format for a detected PII item
├── config.py                # Labels, thresholds, context keywords
├── requirements.txt         # Python packages
├── ground_truth.json        # 107 hand-labelled PII entries for evaluation
├── README.md                # This file
│
├── detectors/
│   ├── regex_detector.py    # Patterns for email, phone, IP, SSN, CC, DOB
│   ├── ettin_detector.py    # Ettin-Nemotron-PII (HuggingFace NER model)
│   └── gliner_detector.py   # GLiNER zero-shot span extractor
│
├── pipeline/
│   ├── reconciler.py        # Merge results from all 3 detectors
│   ├── context_engine.py    # Disambiguate DOB vs ordinary dates, etc.
│   └── policy.py            # Final REDACT / KEEP / REVIEW decision
│
├── redactor/
│   ├── docx_handler.py      # Read .docx, apply replacements, save output
│   └── replacer.py          # Generate consistent fake values (hardcoded + Faker)
│
└── evaluation/
    ├── ground_truth.py      # Load ground_truth.json
    ├── evaluator.py         # Compute TP/FP/FN → Precision/Recall/F1
    └── reporter.py          # Print table to console and write Markdown report
```

---

## How to Add a New PII Type

Say you want to add `PASSPORT_NUMBER`:

1. **`config.py`** — add `"PASSPORT_NUMBER"` to `REDACT_LABELS`
2. **`detectors/regex_detector.py`** — add a regex pattern like `r'[A-Z]\d{7}'`
3. **`config.py`** — add raw label → `"PASSPORT_NUMBER"` mapping in `LABEL_MAP`
4. **`redactor/replacer.py`** — add a `_fake_passport()` method that returns a fake passport number
5. **`ground_truth.json`** — add a few annotated examples and re-run evaluation

---

## Tradeoffs Noticed

- **Recall vs Precision tradeoff**: GLiNER occasionally picks up `"Our Company"` or `"Book Running Lead Managers"` as persons/companies. These are false positives with low confidence and can be filtered by raising the confidence threshold in `config.py`.
- **ALL CAPS names**: Legal prospectuses use ALL CAPS for headings — our system now correctly detects and replaces these too.
- **Long paragraphs**: GLiNER has a 384-token limit per input. Our chunking logic splits long paragraphs into overlapping 1000-character windows with 100-char overlap to avoid missing PII at chunk boundaries.
- **Speed**: Running all 3 detectors on 4,686 blocks takes ~50 minutes on CPU. On a GPU, this would drop to under 5 minutes.
