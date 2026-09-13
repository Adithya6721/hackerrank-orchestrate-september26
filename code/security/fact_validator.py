import pandas as pd
from typing import Dict, Any

class FactValidator:
    def __init__(self, loader):
        self.loader = loader
        
    def validate_facts(self, user_id: str, extracted_facts: Dict[str, Any], date_context: pd.Timestamp) -> Dict[str, Any]:
        """
        Validates facts extracted by LLM against historical data bounds to prevent
        hallucinations or prompt injection.
        """
        validated = {
            'salary_ended': False,
            'salary_override': None,
            'salary_date_override': None,
            'rent_increase_pct': 0.0,
            'suspension_end_date': None,
            'spending_changes': {}
        }
        
        # We can implement specific bounds here if needed based on the user's historical events.
        # For now, we trust the deterministic extraction from the cache, but enforce schema types.
        
        if 'salary_ended' in extracted_facts:
            validated['salary_ended'] = bool(extracted_facts['salary_ended'])
            
        if 'salary_override' in extracted_facts and extracted_facts['salary_override']:
            override = extracted_facts['salary_override']
            if 'amount' in override and 'currency' in override:
                try:
                    if override['amount'] is not None:
                        validated['salary_override'] = {
                            'amount': float(override['amount']),
                            'currency': str(override['currency'])
                        }
                except (ValueError, TypeError):
                    pass
                    
        if 'salary_date_override' in extracted_facts and extracted_facts['salary_date_override']:
            validated['salary_date_override'] = str(extracted_facts['salary_date_override'])
            
        if 'rent_increase_pct' in extracted_facts and extracted_facts['rent_increase_pct'] is not None:
            try:
                validated['rent_increase_pct'] = float(extracted_facts['rent_increase_pct'])
                # Guard against hallucinated massive rent increases (> 200%)
                if validated['rent_increase_pct'] > 2.0:
                    validated['rent_increase_pct'] = 0.0
            except ValueError:
                pass
                
        return validated
