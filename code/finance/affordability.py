from .forecast import simulate_90_days, advance_date
from models.financial_state import FinancialState
from typing import Dict

from models.request import Request

def calculate_safe_amount(state: FinancialState, request: Request, spending_changes: Dict[str, dict] = None) -> float:
    """
    Binary search to find the maximum safe amount that can be paid on day 0
    without breaching the minimum balance.
    """
    min_balance = state.profile.minimum_balance
    
    # Check baseline (pay 0)
    _, min_bal_0 = simulate_90_days(state, 0.0, spending_changes, horizon_days=90)
    
    safe_headroom = max(0.0, min_bal_0 - min_balance)
    return round(min(request.requested_amount, safe_headroom), 2)

def find_earliest_full_payment_date(state: FinancialState, request: Request, spending_changes: Dict[str, dict] = None) -> str:
    """
    Simulate shifting the payment day by day until it's affordable.
    """
    from datetime import timedelta
    min_balance = state.profile.minimum_balance
    req_date = state.request_date
    
    if spending_changes is None:
        spending_changes = {}
        
    scheduled_set = set()
    for event in state.scheduled_events:
        if not event.is_prepaid:
            scheduled_set.add((event.date, event.category, event.direction))
            
    for day_offset in range(91):
        test_date = req_date + timedelta(days=day_offset)
        
        current_balance = state.profile.current_balance
        for pd_amount in state.pending_debits:
            current_balance -= pd_amount
            
        daily_balances = []
        income_dates = {i: inc.next_date for i, inc in enumerate(state.recurring_income)}
        expense_dates = {i: exp.next_date for i, exp in enumerate(state.recurring_expenses)}
        
        for d in range(91):
            current_date = req_date + timedelta(days=d)
            
            if current_date == test_date:
                current_balance -= request.requested_amount
                
            for event in state.scheduled_events:
                if event.date == current_date and event.direction == 'credit':
                    current_balance += event.amount
                    
            for i, inc in enumerate(state.recurring_income):
                if inc.status != 'active': continue
                if income_dates[i] == current_date:
                    if (current_date, inc.category, 'credit') not in scheduled_set:
                        current_balance += inc.amount
                    income_dates[i] = advance_date(income_dates[i], inc.cadence_days)
                        
            for event in state.scheduled_events:
                if event.date == current_date and event.direction == 'debit':
                    if not event.is_prepaid:
                        current_balance -= event.amount
                        
            for i, exp in enumerate(state.recurring_expenses):
                if exp.suspension_end_date and current_date <= exp.suspension_end_date:
                    if expense_dates[i] == current_date:
                        expense_dates[i] = advance_date(expense_dates[i], exp.cadence_days)
                    continue
                    
                if expense_dates[i] == current_date:
                    if (current_date, exp.category, 'debit') not in scheduled_set:
                        if exp.category in spending_changes:
                            change = spending_changes[exp.category]
                            if change['type'] == 'stop': pass
                            elif change['type'] == 'reduce':
                                current_balance -= change['new_amount']
                        else:
                            current_balance -= exp.amount
                    expense_dates[i] = advance_date(expense_dates[i], exp.cadence_days)
                    
            daily_balances.append(current_balance)
            
        if min(daily_balances) >= min_balance:
            return test_date.strftime('%Y-%m-%d')
            
    return None
