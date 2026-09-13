import unittest
import pandas as pd
from datetime import date
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from ingestion.currency import CurrencyConverter

class TestCurrencyConverter(unittest.TestCase):
    def test_currency_conversion(self):
        rates_df = pd.DataFrame([
            {'from_currency': 'USD', 'to_currency': 'IDR', 'rate': 15000.0, 'rate_date': '2026-01-01'},
            {'from_currency': 'IDR', 'to_currency': 'USD', 'rate': 0.00006667, 'rate_date': '2026-01-01'}
        ])
        
        cc = CurrencyConverter(rates_df)
        
        # Same currency
        self.assertEqual(cc.convert(100.0, 'USD', 'USD', date(2026, 1, 15)), 100.0)
        
        # Simple conversion
        converted = cc.convert(10.0, 'USD', 'IDR', date(2026, 1, 15))
        self.assertAlmostEqual(converted, 150000.0, delta=150.0)
        
        # Reverse conversion
        converted_rev = cc.convert(150000.0, 'IDR', 'USD', date(2026, 1, 15))
        self.assertAlmostEqual(converted_rev, 10.0, delta=0.1)

if __name__ == '__main__':
    unittest.main()
