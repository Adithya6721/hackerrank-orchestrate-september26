import pandas as pd
import os
from typing import List, Dict
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if not os.environ.get("GROQ_API_KEY"):
    for p in [".env", os.path.join(os.path.dirname(__file__), "..", ".env")]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GROQ_API_KEY="):
                        os.environ["GROQ_API_KEY"] = line.strip().split("=", 1)[1].strip().strip('"').strip("'")

from ingestion.loader import DataLoader
from ingestion.currency import CurrencyConverter
from ai.fact_extractor import MessageFactExtractor
from ai.image_interpreter import ImageInterpreter
from ai.query_interpreter import QueryInterpreter
from finance.state_builder import StateBuilder
from finance.plan_generator import evaluate_strategies
from finance.ranker import rank_and_select
from models.request import Request, PaymentOption

def main():
    print("Loading data...")
    loader = DataLoader('dataset')
    
    requests_df = loader.get_unseen_requests()
    options_df = loader.get_payment_options()
    
    print(f"Found {len(requests_df)} requests to process.")
    
    cc = CurrencyConverter(loader.get_rates())
    msg_extractor = MessageFactExtractor()
    img_interpreter = ImageInterpreter()
    
    state_builder = StateBuilder(loader, cc, msg_extractor, img_interpreter)
    
    results = []
    
    for _, req_row in requests_df.iterrows():
        req_id = req_row['request_id']
        user_id = req_row['user_id']
        
        # Build request object
        req_options = options_df[options_df['request_id'] == req_id]
        options = []
        for _, opt_row in req_options.iterrows():
            # In a full implementation, date parsing should be robust
            first_pay = pd.to_datetime(opt_row['first_payment_date']).date() if pd.notna(opt_row['first_payment_date']) else None
            options.append(PaymentOption(
                option_id=opt_row['payment_option_id'],
                payment_method=opt_row['payment_method'],
                payment_amount=float(opt_row['payment_amount']),
                number_of_payments=int(opt_row['number_of_payments']),
                first_payment_date=first_pay,
                payment_frequency_days=int(opt_row['payment_frequency_days']) if pd.notna(opt_row['payment_frequency_days']) else None,
                financing_fee=float(opt_row['financing_fee']) if pd.notna(opt_row['financing_fee']) else 0.0,
                total_payable_amount=float(opt_row['total_payable_amount'])
            ))
            
        request = Request(
            request_id=req_id,
            user_id=user_id,
            request_date=req_row['request_date'].date(),
            request_type=req_row['request_type'],
            requested_amount=float(req_row['requested_amount']),
            desired_completion_date=pd.to_datetime(req_row['desired_completion_date']).date(),
            allows_partial_payment=req_row['allows_partial_payment'],
            options=options
        )
        
        # 1. Build Canonical State
        state = state_builder.build_state(user_id, req_id, pd.Timestamp(request.request_date))
        
        # 2. Evaluate Strategies
        strategies = evaluate_strategies(state, request, loader)
        
        # 3. Rank and Select Decision
        decision = rank_and_select(strategies)
        decision.request_id = req_id
        
        results.append({
            'request_id': decision.request_id,
            'amount_safe_to_pay': decision.amount_safe_to_pay,
            'affordability_status': decision.affordability_status,
            'recommended_payment_method': decision.recommended_payment_method,
            'payment_plan': decision.payment_plan,
            'earliest_date_for_full_payment': decision.earliest_date_for_full_payment,
            'spending_changes_needed': decision.spending_changes_needed,
            'decision_explanation': decision.decision_explanation
        })
        
    # Validate and write output
    from validation.output_validator import OutputValidator
    OutputValidator.validate_and_save(results, 'dataset/output.csv')
    OutputValidator.validate_and_save(results, 'output.csv')
    out_df = pd.read_csv('output.csv')
    
    # Also evaluate against requests_df if it has expected values
    if 'amount_safe_to_pay' in requests_df.columns:
        eval_df = out_df.merge(requests_df, on='request_id', suffixes=('_pred', '_expected'))
        matches = 0
        for _, row in eval_df.iterrows():
            err = abs(row['amount_safe_to_pay_pred'] - row['amount_safe_to_pay_expected'])
            if row['amount_safe_to_pay_expected'] > 0:
                pct_err = err / row['amount_safe_to_pay_expected']
            else:
                pct_err = 0 if err == 0 else 1
                
            if pct_err <= 0.05:
                matches += 1
                print(f"OK {row['request_id']}: expected={row['amount_safe_to_pay_expected']} predicted={row['amount_safe_to_pay_pred']}")
            else:
                print(f"XX {row['request_id']}: expected={row['amount_safe_to_pay_expected']} predicted={row['amount_safe_to_pay_pred']} (err: {pct_err*100:.1f}%)")
                
        print(f"\nFinal Score: {matches}/{len(eval_df)}")
    else:
        print(f"\nProcessed {len(out_df)} unseen requests and saved to output.csv")


if __name__ == '__main__':
    main()
