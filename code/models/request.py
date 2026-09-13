from dataclasses import dataclass
from typing import Optional, List
from datetime import date

@dataclass
class PaymentOption:
    option_id: str
    payment_method: str  # 'full_payment', 'installments'
    payment_amount: float
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: Optional[int]
    financing_fee: float
    total_payable_amount: float

@dataclass
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: float
    desired_completion_date: date
    allows_partial_payment: bool
    options: List[PaymentOption]
