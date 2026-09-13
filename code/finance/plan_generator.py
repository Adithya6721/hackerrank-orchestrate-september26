from datetime import timedelta, date
from models.financial_state import FinancialState
from models.request import Request
from .affordability import calculate_safe_amount, find_earliest_full_payment_date
from .forecast import simulate_90_days, advance_date
import pandas as pd

def _format_amt(val: float) -> str:
    if val is None or pd.isna(val):
        return "0"
    val = round(float(val), 2)
    if val.is_integer():
        return f"{int(val)}"
    return f"{val:.2f}"

def _format_comma_amt(val: float) -> str:
    if val is None or pd.isna(val):
        return "0"
    val = round(float(val), 2)
    if val.is_integer():
        return f"{int(val):,}"
    return f"{val:,.2f}"

def _get_flexible_changes(state: FinancialState, data_loader):
    events = data_loader.get_events()
    user_events = events[events['user_id'] == state.profile.user_id].copy()
    user_events['settlement_date'] = pd.to_datetime(user_events['settlement_date'])
    
    changes = {}
    for exp in state.recurring_expenses:
        if exp.flexibility in ('stoppable', 'reducible_or_stoppable', 'reducible'):
            # Find latest settled event for this category to get event_id
            cat_evs = user_events[
                (user_events['category'] == exp.category) & 
                (user_events['direction'] == 'debit') &
                (user_events['settlement_date'] < pd.Timestamp(state.request_date))
            ].sort_values('settlement_date')
            
            latest_id = cat_evs.iloc[-1]['event_id'] if not cat_evs.empty else None
            
            if exp.flexibility in ('stoppable', 'reducible_or_stoppable'):
                changes[exp.category] = {
                    'type': 'stop',
                    'event_id': latest_id,
                    'orig_amount': exp.amount
                }
            elif exp.flexibility == 'reducible':
                changes[exp.category] = {
                    'type': 'reduce',
                    'new_amount': exp.min_allowed,
                    'event_id': latest_id,
                    'orig_amount': exp.amount
                }
    return changes

def _format_changes_string(changes: dict) -> str:
    if not changes:
        return "none"
    parts = []
    for cat, info in changes.items():
        eid = info.get('event_id')
        if not eid:
            continue
        if info['type'] == 'stop':
            parts.append(f"stop:{eid}")
        elif info['type'] == 'reduce':
            amt_str = _format_amt(info['new_amount'])
            parts.append(f"reduce_to:{eid}:{amt_str}")
    return "|".join(parts) if parts else "none"

def _format_changes_text(changes: dict, state: FinancialState) -> str:
    if not changes:
        return ""
    parts = []
    for cat, info in changes.items():
        if info['type'] == 'stop':
            parts.append(f"Stop the {cat.replace('_', ' ')}")
        elif info['type'] == 'reduce':
            amt_str = _format_comma_amt(info['new_amount'])
            curr = state.profile.home_currency
            parts.append(f"Reduce the {cat.replace('_', ' ')} to {curr} {amt_str}")
    return " and ".join(parts)

def evaluate_strategies(state: FinancialState, request: Request, data_loader):
    currency = state.profile.home_currency
    min_bal = state.profile.minimum_balance
    req_amt = request.requested_amount
    req_date_str = request.request_date.strftime('%Y-%m-%d')
    desired_date_str = request.desired_completion_date.strftime('%d %B %Y') if request.desired_completion_date else ""

    baseline_safe = calculate_safe_amount(state, request, spending_changes=None)
    
    # Check 1: Affordable Now (Full Payment today without changes)
    if baseline_safe >= req_amt:
        _, min_bal_headroom = simulate_90_days(state, req_amt, None)
        avail_headroom = max(0.0, min_bal_headroom)
        return {
            'amount_safe_to_pay': req_amt,
            'affordability_status': 'affordable_now',
            'recommended_payment_method': 'full_payment',
            'payment_plan': f"{req_date_str}:{_format_amt(req_amt)}",
            'earliest_date_for_full_payment': req_date_str,
            'spending_changes_needed': 'none',
            'decision_explanation': f"Pay {currency} {_format_comma_amt(req_amt)} today. This leaves at least {currency} {_format_comma_amt(avail_headroom)} available over the next 90 days."
        }
        
    all_changes = _get_flexible_changes(state, data_loader)
    
    # Check 2: Affordable with Plan (Full payment today with spending changes)
    plan_safe = calculate_safe_amount(state, request, spending_changes=all_changes)
    if plan_safe >= req_amt and all_changes:
        needed_changes = {}
        for cat, change_info in all_changes.items():
            test_changes = {**needed_changes, cat: change_info}
            if calculate_safe_amount(state, request, spending_changes=test_changes) >= req_amt:
                needed_changes = test_changes
                break
            needed_changes = test_changes
            
        changes_str = _format_changes_string(needed_changes if needed_changes else all_changes)
        changes_text = _format_changes_text(needed_changes if needed_changes else all_changes, state)
        earliest_d = find_earliest_full_payment_date(state, request, spending_changes=needed_changes)
        _, min_bal_headroom = simulate_90_days(state, req_amt, needed_changes if needed_changes else all_changes)
        avail_headroom = max(0.0, min_bal_headroom)
        return {
            'amount_safe_to_pay': baseline_safe,
            'affordability_status': 'affordable_with_plan',
            'recommended_payment_method': 'full_payment',
            'payment_plan': f"{req_date_str}:{_format_amt(req_amt)}",
            'earliest_date_for_full_payment': earliest_d if earliest_d else req_date_str,
            'spending_changes_needed': changes_str,
            'decision_explanation': f"{changes_text}, then pay {currency} {_format_comma_amt(req_amt)} today. This leaves at least {currency} {_format_comma_amt(avail_headroom)} available."
        }
        
    # Check 3: Partial Payment option (if allowed and earliest full payment date is <= desired completion date)
    earliest_d_no_changes = find_earliest_full_payment_date(state, request, spending_changes=None)
    if request.allows_partial_payment and baseline_safe > 0 and earliest_d_no_changes:
        earliest_d_date = pd.to_datetime(earliest_d_no_changes).date()
        if request.desired_completion_date and earliest_d_date <= request.desired_completion_date:
            remaining_amt = round(req_amt - baseline_safe, 2)
            plan_str = f"{req_date_str}:{_format_amt(baseline_safe)}|{earliest_d_no_changes}:{_format_amt(remaining_amt)}"
            earliest_fmt = earliest_d_date.strftime('%d %B %Y')
            return {
                'amount_safe_to_pay': baseline_safe,
                'affordability_status': 'affordable_with_plan',
                'recommended_payment_method': 'partial_payment',
                'payment_plan': plan_str,
                'earliest_date_for_full_payment': earliest_d_no_changes,
                'spending_changes_needed': 'none',
                'decision_explanation': f"Pay {currency} {_format_comma_amt(baseline_safe)} today and the remaining {currency} {_format_comma_amt(remaining_amt)} on {earliest_fmt}. This completes the full request and keeps the {currency} {_format_comma_amt(min_bal)} minimum protected."
            }

    # Check 4: Installment Options (sort by number of payments ascending to prefer shorter plans e.g. 3 installments over 21)
    installment_options = [opt for opt in request.options if opt.payment_method in ('installments', 'partial_payment') and opt.number_of_payments > 1]
    installment_options.sort(key=lambda o: (o.number_of_payments, o.total_payable_amount))
    
    for opt in installment_options:
        pay_dates = []
        curr_pdate = opt.first_payment_date if opt.first_payment_date else request.request_date
        freq = opt.payment_frequency_days if opt.payment_frequency_days else 30
        for i in range(opt.number_of_payments):
            pay_dates.append((curr_pdate, opt.payment_amount))
            curr_pdate = advance_date(curr_pdate, freq)

        from models.financial_state import ScheduledEvent
        import copy
        test_state = copy.deepcopy(state)
        for pay_d, pay_a in pay_dates:
            test_state.scheduled_events.append(ScheduledEvent(
                event_id=f"_install_{pay_d}",
                date=pay_d,
                amount=pay_a,
                direction='debit',
                category='installment',
                is_prepaid=False
            ))

        _, min_bal_install = simulate_90_days(test_state, 0.0, None)
        if min_bal_install < state.profile.minimum_balance:
            continue

        plan_str = "|".join([
            f"{d.strftime('%Y-%m-%d')}:{_format_amt(a)}"
            for d, a in pay_dates
        ])
        first_pay_fmt = pay_dates[0][0].strftime('%d %B %Y') if pay_dates else req_date_str
        avail_headroom = max(0.0, min_bal_install)
        return {
            'amount_safe_to_pay': baseline_safe,
            'affordability_status': 'affordable_with_plan',
            'recommended_payment_method': 'installments',
            'payment_plan': plan_str,
            'earliest_date_for_full_payment': earliest_d_no_changes if earliest_d_no_changes else req_date_str,
            'spending_changes_needed': 'none',
            'decision_explanation': f"Use {opt.number_of_payments} installments of {currency} {_format_comma_amt(opt.payment_amount)}, starting {first_pay_fmt}. This leaves at least {currency} {_format_comma_amt(avail_headroom)} available."
        }
            
    # Check 5: Affordable Later (Wait for next income/cashflow)
    if earliest_d_no_changes:
        earliest_fmt = pd.to_datetime(earliest_d_no_changes).date().strftime('%d %B %Y')
        return {
            'amount_safe_to_pay': baseline_safe,
            'affordability_status': 'affordable_later',
            'recommended_payment_method': 'wait',
            'payment_plan': f"{earliest_d_no_changes}:{_format_amt(req_amt)}",
            'earliest_date_for_full_payment': earliest_d_no_changes,
            'spending_changes_needed': 'none',
            'decision_explanation': f"Pay {currency} {_format_comma_amt(req_amt)} in full on {earliest_fmt}. Paying earlier would take the balance below the {currency} {_format_comma_amt(min_bal)} minimum."
        }
        
    # Check 6: Not Affordable
    return {
        'amount_safe_to_pay': baseline_safe,
        'affordability_status': 'not_affordable',
        'recommended_payment_method': 'not_recommended',
        'payment_plan': 'none',
        'earliest_date_for_full_payment': None,
        'spending_changes_needed': 'none',
        'decision_explanation': f"Do not make this payment by {desired_date_str}. None of the available options keeps the {currency} {_format_comma_amt(min_bal)} minimum protected."
    }
