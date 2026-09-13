import os
import json
import time

IMAGE_EXTRACTION_PROMPT = """
You are a financial document parser.
Analyze this document image and extract the essential transaction amount.
Determine whether it is a receipt, invoice, or payslip.

Respond with a JSON object:
{
    "financial_amount": 0.0,
    "currency": "USD",
    "document_type": "invoice"
}
"""

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

class ImageInterpreter:
    def __init__(self, cache_file: str = "groq_cache_images.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.api_key = _resolve_groq_key()
        if self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                self.model = "qwen/qwen3.8-27b"
                print(f"[GROQ VISION INIT] Initialized Groq Vision client with model '{self.model}'.")
            except Exception as e:
                print(f"[GROQ VISION INIT ERROR] Could not initialize Groq vision client: {e}")
                self.client = None
        else:
            print("[GROQ VISION INIT] No valid GROQ_API_KEY found in environment or .env file.")
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

    def extract_image(self, image_id: str, image_path: str) -> dict:
        if image_id in self.cache:
            print(f"[GROQ VISION CACHE] Using cached extraction for {image_id}")
            return self.cache[image_id]

        if self.client and os.path.exists(image_path):
            print(f"[GROQ VISION API CALL] Live calling Groq VLM ({self.model}) for {image_id} ({image_path})...")
            try:
                import base64
                with open(image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": IMAGE_EXTRACTION_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{base64_image}",
                                    }
                                }
                            ]
                        }
                    ],
                    max_completion_tokens=600,
                    temperature=0.0
                )
                raw_text = response.choices[0].message.content.strip()
                
                # Extract JSON substring from response
                json_str = raw_text
                if "```json" in json_str:
                    json_str = json_str.split("```json", 1)[1].split("```", 1)[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```", 1)[1].split("```", 1)[0].strip()
                elif "</think>" in json_str:
                    json_str = json_str.split("</think>", 1)[1].strip()

                import re
                match = re.search(r'\{[^{}]*\}', json_str, re.DOTALL)
                if match:
                    facts = json.loads(match.group(0))
                else:
                    facts = json.loads(json_str)

                print(f"[GROQ VISION API SUCCESS] Extracted for {image_id}: {facts}")
                self.cache[image_id] = facts
                self._save_cache()
                time.sleep(2.5)  # Rate limit: 24 requests per minute
                return facts
            except Exception as e:
                print(f"[GROQ VISION API ERROR] VLM extraction failed for {image_id}: {e}")
                time.sleep(2.5)  # Sleep on error as well
                
        reason = f"Image file not found at '{image_path}'" if not os.path.exists(image_path) else ("Groq client not initialized" if not self.client else "Groq API error")
        print(f"[GROQ VISION FALLBACK] Using empty default for {image_id} (Reason: {reason})")
        return {"financial_amount": 0.0, "currency": "", "document_type": "unknown"}
