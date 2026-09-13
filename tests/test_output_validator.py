import unittest
import pandas as pd
import tempfile
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from validation.output_validator import OutputValidator

class TestOutputValidator(unittest.TestCase):
    def test_output_validator_valid_schema(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "output.csv")
            
            results = [
                {
                    'request_id': 'req_01',
                    'amount_safe_to_pay': 100.0,
                    'affordability_status': 'affordable_now',
                    'recommended_payment_method': 'full_payment',
                    'payment_plan': '2026-09-01:100',
                    'earliest_date_for_full_payment': '2026-09-01',
                    'spending_changes_needed': 'none',
                    'decision_explanation': 'Test explanation'
                }
            ]
            
            OutputValidator.validate_and_save(results, out_file)
            
            df = pd.read_csv(out_file)
            self.assertEqual(len(df), 1)
            self.assertEqual(list(df.columns), OutputValidator.REQUIRED_COLUMNS)
            self.assertEqual(df.iloc[0]['request_id'], 'req_01')
            self.assertEqual(df.iloc[0]['amount_safe_to_pay'], 100.0)

if __name__ == '__main__':
    unittest.main()
