import unittest
from datetime import date
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from models.financial_state import BaseProfile, FinancialState, RecurringIncome, RecurringExpense, ScheduledEvent
from finance.forecast import advance_date, simulate_90_days

class TestForecast(unittest.TestCase):
    def test_advance_date(self):
        # 7-day cadence
        self.assertEqual(advance_date(date(2026, 9, 1), 7), date(2026, 9, 8))
        
        # Monthly cadence across end of month
        self.assertEqual(advance_date(date(2026, 1, 31), 30), date(2026, 2, 28))
        self.assertEqual(advance_date(date(2026, 8, 15), 30), date(2026, 9, 15))

    def test_simulate_90_days_simple(self):
        profile = BaseProfile(user_id="user_test", current_balance=1000.0, minimum_balance=200.0, home_currency="USD")
        state = FinancialState(profile=profile, request_date=date(2026, 9, 1))
        
        # Add monthly income of $300 on Sep 15 (matches rent expense)
        state.recurring_income.append(RecurringIncome(category="salary", amount=300.0, cadence_days=30, next_date=date(2026, 9, 15)))
        
        # Add monthly rent of $300 on Sep 10
        state.recurring_expenses.append(RecurringExpense(category="rent", amount=300.0, cadence_days=30, next_date=date(2026, 9, 10), flexibility="fixed", min_allowed=0.0))
        
        # Baseline simulation with 0 payment
        daily_bals, min_bal = simulate_90_days(state, payment_amount=0.0)
        
        # Day 0: 1000
        # Sep 10: 1000 - 300 = 700
        # Sep 15: 700 + 300 = 1000
        self.assertEqual(daily_bals[0], 1000.0)
        self.assertEqual(min_bal, 700.0)

    def test_simulate_90_days_with_payment(self):
        profile = BaseProfile(user_id="user_test", current_balance=1000.0, minimum_balance=200.0, home_currency="USD")
        state = FinancialState(profile=profile, request_date=date(2026, 9, 1))
        
        # Monthly income of $300 on Sep 15 balances monthly rent of $300 on Sep 10
        state.recurring_income.append(RecurringIncome(category="salary", amount=300.0, cadence_days=30, next_date=date(2026, 9, 15)))
        state.recurring_expenses.append(RecurringExpense(category="rent", amount=300.0, cadence_days=30, next_date=date(2026, 9, 10), flexibility="fixed", min_allowed=0.0))
        
        # Payment of $600 on day 0
        daily_bals, min_bal = simulate_90_days(state, payment_amount=600.0)
        
        # Day 0: 1000 - 600 = 400
        # Sep 10: 400 - 300 = 100 (breaches minimum balance of 200)
        self.assertEqual(daily_bals[0], 400.0)
        self.assertEqual(min_bal, 100.0)

if __name__ == '__main__':
    unittest.main()
