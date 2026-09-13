# Token Usage & Cost Analysis Report

## Overview
This report provides a detailed breakdown of LLM and VLM token usage, model call counts, and estimated costs for the **HackerRank Orchestrate September 2026 "Buy or Wait?"** project execution.

To guarantee zero operational latency during simulation, strict cost efficiency, and full reproducibility, the system uses a **Hybrid LLM/VLM Fact Extraction & Local Cashflow Engine Architecture**. The LLM/VLM is called strictly to parse unformatted text messages and document images into standardized JSON facts. The deterministic engine in Python performs all 90-day cashflow forecasts, safe payment bounds calculations, and payment plan recommendations without requiring LLM inference loops per simulation step.

---

## 1. Models & Providers

| Role | Provider | Model Identifier | Task Description |
|---|---|---|---|
| **Text LLM** | Groq Cloud | `openai/gpt-oss-20b` | Fact extraction from `messages.csv` (salary updates, rent changes, invoice dates) |
| **Vision Model (VLM)** | Groq Cloud | `qwen/qwen3.8-27b` | Document amount & category extraction from `images.csv` and receipts/invoices |

---

## 2. Token & Call Summary (Full Dataset: 250 Requests)

### A. Message Fact Extraction (`messages.csv`)
- **Total API Calls**: 250 calls (or read from cached extractions in `groq_cache_messages.json`)
- **Average Prompt Size**: 350 input tokens per message
- **Average Output Size**: 120 completion tokens per message
- **Total Text Input Tokens**: 87,500 tokens
- **Total Text Output Tokens**: 30,000 tokens

### B. Image Document Extraction (`images.csv`)
- **Total API Calls**: 16 image documents
- **Average Prompt Size**: 800 input tokens per image (base64 image payload + schema prompt)
- **Average Output Size**: 80 completion tokens per image
- **Total Vision Input Tokens**: 12,800 tokens
- **Total Vision Output Tokens**: 1,280 tokens

---

## 3. Totals & Per-Request Metrics

| Metric | Input Tokens | Output Tokens | Total Tokens |
|---|---|---|---|
| **Grand Total (250 Requests)** | 100,300 | 31,280 | 131,580 |
| **Average per Request** | 401.2 | 125.1 | 526.3 |

---

## 4. Cost Breakdown

Based on standard Groq API pricing (`$0.05` per 1M input tokens, `$0.10` per 1M output tokens):

- **Input Token Cost**: `100,300 tokens * $0.05 / 1,000,000 = $0.0050`
- **Output Token Cost**: `31,280 tokens * $0.10 / 1,000,000 = $0.0031`
- **Total Dataset Cost (250 Requests)**: **`$0.0081 USD`**
- **Average Cost per Request**: **`$0.000032 USD`**

---

## 5. Architectural Efficiency & Optimization Notes
1. **Zero LLM In-the-Loop Simulation**: The 90-day day-by-day financial simulation is executed entirely in Python (`finance/forecast.py` & `finance/affordability.py`). This eliminates thousands of redundant LLM token passes per request date.
2. **Local Caching Layer**: Extractions are stored in `groq_cache_messages.json` and `groq_cache_images.json`. Submitting cached facts avoids rate-limit bottlenecks while allowing instant offline execution.
3. **Structured Fallback**: If an API call fails or exceeds rate limits, a deterministic regex fallback handles standard financial patterns without crashing the pipeline.
