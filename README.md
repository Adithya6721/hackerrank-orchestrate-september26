# HackerRank Orchestrate (September 2026) — "Buy or Wait?"

**Team Solution: Deterministic AI Financial Agent**

This repository contains the complete, production-grade implementation for the HackerRank Orchestrate September 2026 hackathon challenge: **"Buy or Wait?"**.

The system implements a hybrid architecture: **LLM Multimodal Extraction + Deterministic Financial Engine**. The LLM interprets natural language text messages and OCR receipt/pay-stub images into structured financial facts, while a pure Python deterministic engine simulates 90-day cashflows, enforces safety constraints, generates payment plans, and ranks recommendations.

---

## 1. System Architecture & Approach Overview

```
                                    +-----------------------------------+
                                    |        dataset/ Input Files       |
                                    | (requests, profiles, events, etc) |
                                    +-----------------+-----------------+
                                                      |
                                                      v
                                    +-----------------+-----------------+
                                    |   Multimodal Extraction (Groq)    |
                                    |  - Messages: openai/gpt-oss-20b   |
                                    |  - Images: qwen/qwen3.8-27b       |
                                    +-----------------+-----------------+
                                                      |
                                                      v
                                    +-----------------+-----------------+
                                    |   Deterministic Financial Engine  |
                                    |  1. Data Ingestion & Currency BFS |
                                    |  2. 90-Day Cashflow Forecast      |
                                    |  3. Strategy Candidate Generation |
                                    |  4. Multi-Criteria Ranking Tree   |
                                    +-----------------+-----------------+
                                                      |
                                                      v
                                    +-----------------+-----------------+
                                    |  Output Validation & CSV Writer   |
                                    |    Generates dataset/output.csv   |
                                    +-----------------------------------+
```

### Key Modules:
- **`code/ai/`**: Multimodal extraction layer. Uses `openai/gpt-oss-20b` for extracting financial facts from text messages (`messages.csv`) and `qwen/qwen3.8-27b` for vision OCR on receipts/payslips (`images.csv`).
- **`code/ingestion/`**: Data loader and currency converter using Breadth-First Search (BFS) graph traversal across `exchange_rates.csv` for bidirectional currency conversions.
- **`code/finance/state_builder.py`**: Merges static profiles, transaction histories, LLM-extracted facts, and salary events into unified per-user 90-day financial projections.
- **`code/finance/forecast.py`**: Simulates daily cash balances for 90 days, calculating `amount_safe_to_pay` and `earliest_date_for_full_payment` while strictly protecting `minimum_balance_to_keep`.
- **`code/finance/plan_generator.py`**: Evaluates immediate full payments, partial-payment schedules, merchant installment offers (`request_payment_options.csv`), and spending changes (stop/reduce flexible categories).
- **`code/finance/ranker.py`**: Applies the official multi-criteria tie-breaking rules to select the optimal safe plan.
- **`code/validation/output_validator.py`**: Programmatically validates output rows against output bounds and schema rules before writing to CSV.

---

## 2. Setup & Execution Instructions

### Prerequisites
- **Python**: Version 3.10 or higher.
- **Groq API Key**: Set in `.env` or passed via environment variable.

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and add your Groq API key:
```bash
cp .env.example .env
```
Edit `.env`:
```text
GROQ_API_KEY=your_actual_groq_api_key_here
```

### Step 3: Run Full Evaluation Pipeline
To process all 250 requests in `dataset/requests.csv` and generate `output.csv`:
```bash
python code/main.py
```
This execution:
1. Loads all input datasets from `dataset/`.
2. Extracts facts via LLM (with cached local fallback protection).
3. Executes the 90-day deterministic financial engine.
4. Validates and writes results to both `output.csv` and `dataset/output.csv`.

---

## 3. Running Unit Tests

A comprehensive native Python unit test suite is included under `tests/`.

To run all 7 unit tests:
```bash
python -m unittest discover -s tests
```

### Test Coverage:
- **`test_currency.py`**: BFS exchange rate conversion, cross-currency pairs, and identity conversions.
- **`test_forecast.py`**: 90-day cashflow simulation, balance forecasting, and minimum balance protection.
- **`test_plan_generator.py`**: Full payment, partial payment, installment matching, and spending change candidate generation.
- **`test_output_validator.py`**: CSV output bounds, date formatting, and schema validation.

---

## 4. Repository Structure

```text
.
├── AGENTS.md                         # AGENTS.md guidelines and logging rules
├── README.md                         # Setup and architecture documentation
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment template
├── output.csv                        # Generated 250 request predictions
├── log.txt                           # Engineering development transcript
├── chat_transcript.txt               # Copy of log.txt for HackerRank upload slot
├── code.zip                          # Submission ZIP package
├── code/                             # Python source code
│   ├── main.py                       # Pipeline entry point
│   ├── ai/                           # Multimodal extraction (fact_extractor, image_interpreter)
│   ├── finance/                      # Financial engine (state_builder, forecast, plan_generator, ranker)
│   ├── ingestion/                    # Ingestion & currency graph converter
│   ├── models/                       # Dataclasses (financial_state, decision, request)
│   ├── security/                     # Fact validator
│   ├── evaluation/                   # Token usage report (usage_report.md)
│   └── validation/                   # Output schema validator
├── dataset/                          # Challenge datasets (requests.csv, profiles, events, etc.)
├── evaluation/                       # Token & cost analysis report (usage_report.md)
└── tests/                            # Unit test suite
```

---

## 5. Token Usage & Cost Analysis

Per challenge rules, the token usage report for the full 250-request run is documented in:
- **[`evaluation/usage_report.md`](./evaluation/usage_report.md)**

### Summary:
- **Models Used**: `openai/gpt-oss-20b` (text) and `qwen/qwen3.8-27b` (vision).
- **Total Model Calls**: 250 requests.
- **Total Tokens**: ~131,200 tokens.
- **Total Cost**: **~$0.008 USD** (less than 1 cent total).

---

## 6. Deliverables & Submission Checklist

- [x] **`output.csv`**: Contains 250 predictions matching `dataset/requests.csv`. All columns, bounds, and YYYY-MM-DD dates verified.
- [x] **`code.zip`**: Complete runnable solution package containing `code/`, `tests/`, `evaluation/usage_report.md`, `README.md`, `AGENTS.md`, `requirements.txt`, and `.env.example`.
- [x] **`chat_transcript`**: Detailed development log ([`log.txt`](./log.txt) / [`chat_transcript.txt`](./chat_transcript.txt)) uploaded to the submission slot.

Submission URL: https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission
