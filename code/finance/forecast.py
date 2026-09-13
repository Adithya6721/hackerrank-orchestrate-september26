from datetime import timedelta, date
from models.financial_state import FinancialState
from typing import Dict, List, Tuple

def advance_date(curr_d: date, cadence: int) -> date:
    if cadence == 7:
        return curr_d + timedelta(days=7)
    elif cadence == 14:
        return curr_d + timedelta(days=14)
    elif cadence >= 28 and cadence <= 31:
        year = curr_d.year
        month = curr_d.month + 1
        if month > 12:
            month = 1
            year += 1
        day = curr_d.day
        if month == 2:
            max_d = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
            day = min(day, max_d)
        elif month in [4, 6, 9, 11]:
            day = min(day, 30)
        return date(year, month, day)
    else:
        return curr_d + timedelta(days=cadence)

def simulate_90_days(
    state: FinancialState, 
    payment_amount: float, 
    spending_changes: Dict[str, dict] = None,
    horizon_days: int = 90
) -> Tuple[List[float], float]:
    """
    Simulate balance over horizon_days, applying payment_amount on day 0.
    Returns the daily balances and the minimum balance reached.
    """
    if spending_changes is None:
        spending_changes = {}
        
    req_date = state.request_date
    current_balance = state.profile.current_balance
    
    # Deduct pending debits immediately
    for pd_amount in state.pending_debits:
        current_balance -= pd_amount
        
    # Build set of scheduled events to prevent double-counting of recurring
    scheduled_set = set()
    for event in state.scheduled_events:
        if not event.is_prepaid:
            scheduled_set.add((event.date, event.category, event.direction))
            
    daily_balances = []
    
    # Copy next dates to mutate them during simulation
    income_dates = {i: inc.next_date for i, inc in enumerate(state.recurring_income)}
    expense_dates = {i: exp.next_date for i, exp in enumerate(state.recurring_expenses)}
    
    for day_offset in range(horizon_days + 1):
        current_date = req_date + timedelta(days=day_offset)
        
        # Apply the requested payment on day 0
        if day_offset == 0:
            current_balance -= payment_amount
            
        # Add scheduled income
        for event in state.scheduled_events:
            if event.date == current_date and event.direction == 'credit':
                current_balance += event.amount
                
        # Add recurring income
        for i, inc in enumerate(state.recurring_income):
            if inc.status != 'active':
                continue
            if income_dates[i] == current_date:
                if (current_date, inc.category, 'credit') not in scheduled_set:
                    current_balance += inc.amount
                income_dates[i] = advance_date(income_dates[i], inc.cadence_days)
                    
        # Deduct scheduled expenses
        for event in state.scheduled_events:
            if event.date == current_date and event.direction == 'debit':
                if not event.is_prepaid:
                    current_balance -= event.amount
                
        # Deduct recurring expenses
        for i, exp in enumerate(state.recurring_expenses):
            # Check suspension (prepaid)
            if exp.suspension_end_date and current_date <= exp.suspension_end_date:
                if expense_dates[i] == current_date:
                    expense_dates[i] = advance_date(expense_dates[i], exp.cadence_days)
                continue
                
            if expense_dates[i] == current_date:
                if (current_date, exp.category, 'debit') not in scheduled_set:
                    if exp.category in spending_changes:
                        change = spending_changes[exp.category]
                        if change['type'] == 'stop':
                            pass # don't deduct
                        elif change['type'] == 'reduce':
                            current_balance -= change['new_amount']
                    else:
                        current_balance -= exp.amount
                
                expense_dates[i] = advance_date(expense_dates[i], exp.cadence_days)
                
        daily_balances.append(current_balance)
        
    return daily_balances, min(daily_balances)
