from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import date

@dataclass
class RecurringIncome:
    category: str
    amount: float
    cadence_days: int
    next_date: date
    status: str = "active"

@dataclass
class RecurringExpense:
    category: str
    amount: float
    cadence_days: int # 7, 14, 30
    next_date: date
    flexibility: str  # 'fixed', 'reducible', 'stoppable', 'reducible_or_stoppable'
    min_allowed: float = 0.0
    suspension_end_date: Optional[date] = None

@dataclass
class ScheduledEvent:
    event_id: str
    date: date
    amount: float
    direction: str  # 'credit', 'debit'
    category: str
    is_prepaid: bool = False

@dataclass
class BaseProfile:
    user_id: str
    current_balance: float
    minimum_balance: float
    home_currency: str

@dataclass
class FinancialState:
    profile: BaseProfile
    recurring_income: List[RecurringIncome] = field(default_factory=list)
    recurring_expenses: List[RecurringExpense] = field(default_factory=list)
    scheduled_events: List[ScheduledEvent] = field(default_factory=list)
    pending_debits: List[float] = field(default_factory=list)
    
    # Track the exact date we simulate from
    request_date: Optional[date] = None
