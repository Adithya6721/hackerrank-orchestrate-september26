import pandas as pd
from typing import List, Dict, Any

class OutputValidator:
    REQUIRED_COLUMNS = [
        'request_id',
        'amount_safe_to_pay',
        'affordability_status',
        'recommended_payment_method',
        'payment_plan',
        'earliest_date_for_full_payment',
        'spending_changes_needed',
        'decision_explanation'
    ]
    
    ALLOWED_STATUS = ['affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable']
    ALLOWED_METHODS = ['full_payment', 'installments', 'partial_payment', 'wait', 'not_recommended']

    @classmethod
    def validate_and_save(cls, results: List[Dict[str, Any]], filepath: str):
        df = pd.DataFrame(results)
        
        # Check columns
        for col in cls.REQUIRED_COLUMNS:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
                
        # Fill NA with specific rules
        df['amount_safe_to_pay'] = df['amount_safe_to_pay'].fillna(0.0).round(2)
        df['affordability_status'] = df['affordability_status'].fillna('not_affordable')
        df['recommended_payment_method'] = df['recommended_payment_method'].fillna('not_recommended')
        df['payment_plan'] = df['payment_plan'].fillna('none')
        df['earliest_date_for_full_payment'] = df['earliest_date_for_full_payment'].fillna('')
        df['spending_changes_needed'] = df['spending_changes_needed'].fillna('none')
        df['decision_explanation'] = df['decision_explanation'].fillna('')
        
        # Validate Enums
        if not df['affordability_status'].isin(cls.ALLOWED_STATUS).all():
            print("WARNING: Invalid affordability_status detected")
        if not df['recommended_payment_method'].isin(cls.ALLOWED_METHODS).all():
            print("WARNING: Invalid recommended_payment_method detected")
            
        # Ensure only required columns are saved
        df = df[cls.REQUIRED_COLUMNS]
        df.to_csv(filepath, index=False)
        print(f"Validated and saved {len(df)} records to {filepath}")
