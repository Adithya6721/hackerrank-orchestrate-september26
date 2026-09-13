from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class Decision:
    request_id: str
    amount_safe_to_pay: float = 0.0
    affordability_status: str = "not_affordable"
    recommended_payment_method: str = "not_recommended"
    payment_plan: str = "none"
    earliest_date_for_full_payment: Optional[str] = None
    spending_changes_needed: str = "none"
    decision_explanation: str = "none"
