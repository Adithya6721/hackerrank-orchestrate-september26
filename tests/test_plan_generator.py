import unittest
from datetime import date
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from models.financial_state import BaseProfile, FinancialState, RecurringIncome, RecurringExpense
from models.request import Request, PaymentOption
from finance.affordability import calculate_safe_amount
from finance.plan_generator import evaluate_strategies

class MockDataLoader:
    def get_events(self):
        import pandas as pd
        return pd.DataFrame(columns=['user_id', 'category', 'direction', 'settlement_date', 'event_id'])

class TestPlanGenerator(unittest.TestCase):
    def test_calculate_safe_amount(self):
        profile = BaseProfile(user_id="user_test", current_balance=1000.0, minimum_balance=200.0, home_currency="USD")
        state = FinancialState(profile=profile, request_date=date(2026, 9, 1))
        
        # Income of $300 on Sep 15 balances rent of $300 on Sep 10
        state.recurring_income.append(RecurringIncome(category="salary", amount=300.0, cadence_days=30, next_date=date(2026, 9, 15)))
        state.recurring_expenses.append(RecurringExpense(category="rent", amount=300.0, cadence_days=30, next_date=date(2026, 9, 10), flexibility="fixed", min_allowed=0.0))
        
        req = Request(
            request_id="req_01",
            user_id="user_test",
            request_date=date(2026, 9, 1),
            request_type="purchase",
            requested_amount=1000.0,
            desired_completion_date=date(2026, 9, 1),
            allows_partial_payment=False,
            options=[]
        )
        
        # Min balance reached over 90 days without purchase = 700.0
        # Min balance required = 200.0
        # Safe headroom = 700 - 200 = 500.0
        safe_amt = calculate_safe_amount(state, req)
        self.assertEqual(safe_amt, 500.0)

    def test_evaluate_strategies_affordable_now(self):
        profile = BaseProfile(user_id="user_test", current_balance=1000.0, minimum_balance=200.0, home_currency="USD")
        state = FinancialState(profile=profile, request_date=date(2026, 9, 1))
        
        req = Request(
            request_id="req_01",
            user_id="user_test",
            request_date=date(2026, 9, 1),
            request_type="purchase",
            requested_amount=500.0,
            desired_completion_date=date(2026, 9, 1),
            allows_partial_payment=False,
            options=[]
        )
        
        res = evaluate_strategies(state, req, MockDataLoader())
        self.assertEqual(res['affordability_status'], 'affordable_now')
        self.assertEqual(res['recommended_payment_method'], 'full_payment')
        self.assertEqual(res['amount_safe_to_pay'], 500.0)

if __name__ == '__main__':
    unittest.main()
