import os
import json
import re
import time

MESSAGE_EXTRACTION_PROMPT = """You are a financial data extraction AI.
Read the message and extract any updates to financial state.
Always return a raw JSON object with these fields:
{
  "salary_override": {"amount": 0.0, "currency": "USD", "effective_date": "YYYY-MM-DD"},
  "salary_ended": false,
  "salary_date_override": "YYYY-MM-DD",
  "confirmed_income": [{"amount": 0.0, "currency": "USD", "expected_date": "YYYY-MM-DD"}],
  "rent_increase_pct": 0.0,
  "arrears": {"amount": 0.0, "currency": "USD"},
  "new_deductions": []
}
Use null/false/empty list for unused fields. Output valid JSON only."""

def _resolve_groq_key() -> str:
    key = os.environ.get("GROQ_API_KEY")
    if key and not key.startswith("your_"):
        return key.strip()
    candidates = [
        ".env",
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), ".env")
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GROQ_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val and not val.startswith("your_"):
                                os.environ["GROQ_API_KEY"] = val
                                return val
            except Exception:
                pass
    return None

class MessageFactExtractor:
    def __init__(self, cache_file: str = "groq_cache_messages.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.api_key = _resolve_groq_key()
        if self.api_key:
            try:
                # pyrefly: ignore [missing-import]
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                self.model = "openai/gpt-oss-20b"
                print(f"[GROQ INIT] Initialized Groq LLM client with model '{self.model}'.")
            except Exception as e:
                print(f"[GROQ INIT ERROR] Could not initialize Groq client: {e}")
                self.client = None
        else:
            print("[GROQ INIT] No valid GROQ_API_KEY found in environment or .env file.")
            self.client = None

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception:
            pass

    def _fallback_regex_extract(self, text: str) -> dict:
        result = {
            "salary_override": None,
            "salary_ended": False,
            "salary_date_override": None,
            "confirmed_income": [],
            "rent_increase_pct": None,
            "arrears": None,
            "new_deductions": []
        }
        
        def clean_amount(s: str) -> float:
            s = s.replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace('Rp', '').replace(',', '').strip()
            try:
                return float(s)
            except ValueError:
                return 0.0

        # Rent increase
        m = re.search(r'rent.*?increased?.*?(?:by|sebesar)\s+(\d+(?:\.\d+)?)\s*%', text, re.IGNORECASE)
        if m:
            result['rent_increase_pct'] = float(m.group(1)) / 100.0

        # Salary increase
        m = re.search(r'(?:salary|gaji)\s+(?:.*?(?:increased?|naik|now)\s+(?:to|menjadi)\s+)(\w+)\s+([\d,\.]+)', text, re.IGNORECASE)
        if m:
            curr = m.group(1)
            amt = clean_amount(m.group(2))
            d = re.search(r'(?:from|mulai|applies from)\s+(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
            result['salary_override'] = {"amount": amt, "currency": curr, "effective_date": d.group(1) if d else None}

        # Confirmed invoice payment
        m = re.search(r'invoice.*?payment of (\w+)\s+([\d,\.]+)', text, re.IGNORECASE)
        if not m:
            m = re.search(r'pembayaran.*?(?:sebesar\s+)?(\w+)\s+([\d,\.]+)\s+telah\s+disetujui', text, re.IGNORECASE)
        if m:
            curr = m.group(1)
            amt = clean_amount(m.group(2))
            d = re.search(r'(?:settlement.*?expected\s+on|diperkirakan pada)\s+(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
            result['confirmed_income'].append({"amount": amt, "currency": curr, "expected_date": d.group(1) if d else None})

        # Temporary reduced salary
        m = re.search(r'temporary monthly pay\s+(?:is\s+)?(\w+)\s+([\d,\.]+)', text, re.IGNORECASE)
        if m:
            result['salary_override'] = {"amount": clean_amount(m.group(2)), "currency": m.group(1), "effective_date": None}

        # Salary date override
        m = re.search(r'salary\s+(?:sebesar\s+)?(\w+)\s+([\d,\.]+)\s+dikonfirmasi\s+untuk\s+(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
        if m:
            result['salary_override'] = {"amount": clean_amount(m.group(2)), "currency": m.group(1), "effective_date": m.group(3)}
            result['salary_date_override'] = m.group(3)

        # Salary ended
        if 'employment has ended' in text.lower() or 'berhenti bekerja' in text.lower():
            result['salary_ended'] = True

        return result

    def extract_facts(self, message_id: str, message_text: str) -> dict:
        if message_id in self.cache:
            print(f"[GROQ CACHE] Using cached message facts for {message_id}")
            return self.cache[message_id]

        if self.client:
            print(f"[GROQ API CALL] Live calling Groq ({self.model}) for {message_id}...")
            prompt = f"{MESSAGE_EXTRACTION_PROMPT}\n\nMessage:\n{message_text}"
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a financial data extraction AI. Output valid JSON object only."},
                        {"role": "user", "content": prompt}
                    ],
                    max_completion_tokens=1000,
                    temperature=0.0
                )
                raw_text = response.choices[0].message.content.strip()
                json_str = raw_text
                if "```json" in json_str:
                    json_str = json_str.split("```json", 1)[1].split("```", 1)[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```", 1)[1].split("```", 1)[0].strip()
                
                match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_str, re.DOTALL)
                if match:
                    facts = json.loads(match.group(0))
                else:
                    facts = json.loads(json_str)

                print(f"[GROQ API SUCCESS] Extracted for {message_id}: {facts}")
                self.cache[message_id] = facts
                self._save_cache()
                time.sleep(2.5)  # Rate limit: 24 requests per minute
                return facts
            except Exception as e:
                print(f"[GROQ API ERROR] Groq call failed for {message_id}: {e}")
                time.sleep(2.5)  # Sleep on error as well to prevent spamming
                
        # Fallback to regex if Groq fails or API key missing
        reason = "Groq client not initialized / key missing" if not self.client else "API call error"
        print(f"[GROQ FALLBACK] Using regex for {message_id} (Reason: {reason})")
        return self._fallback_regex_extract(message_text)
