import pandas as pd
import numpy as np
from datetime import timedelta, date
from models.financial_state import BaseProfile, FinancialState, RecurringIncome, RecurringExpense, ScheduledEvent
from ingestion.currency import CurrencyConverter
from finance.forecast import advance_date

class StateBuilder:
    def __init__(self, data_loader, currency_converter: CurrencyConverter, message_extractor, image_interpreter):
        self.data = data_loader
        self.loader = data_loader
        self.cc = currency_converter
        self.msg_extractor = message_extractor
        self.img_interpreter = image_interpreter
        
        from security.fact_validator import FactValidator
        self.fact_validator = FactValidator(data_loader)

    def build_state(self, user_id: str, request_id: str, req_date: pd.Timestamp) -> FinancialState:
        # Load profile
        profiles = self.loader.get_profiles()
        profile_row = profiles[profiles['user_id'] == user_id].iloc[0]
        home_currency = profile_row['home_currency']
        
        # Load events
        all_events = self.data.get_events()
        user_events = all_events[all_events['user_id'] == user_id].copy()
        user_events['settlement_date'] = pd.to_datetime(user_events['settlement_date'])
        
        # Parse images and fill missing amounts
        images = self.data.get_images()
        user_images = images[(images['user_id'] == user_id)]
        
        image_facts = {}
        for _, img_row in user_images.iterrows():
            img_id = img_row['image_id']
            facts = self.img_interpreter.extract_image(img_id, f"dataset/media/images/{img_id}.png")
            if not pd.isna(img_row['related_event_id']):
                image_facts[img_row['related_event_id']] = facts
                
                # Patch missing amounts in user_events
                mask = user_events['event_id'] == img_row['related_event_id']
                if mask.any() and (pd.isna(user_events.loc[mask, 'amount'].values[0]) or user_events.loc[mask, 'amount'].values[0] == 0):
                    user_events.loc[mask, 'amount'] = facts.get('financial_amount', 0.0)
                    if pd.isna(user_events.loc[mask, 'currency'].values[0]):
                        user_events.loc[mask, 'currency'] = facts.get('currency', home_currency)
        
        # Parse messages for this user prior to or on request date
        messages = self.data.get_messages()
        msg_sent = pd.to_datetime(messages['sent_at'])
        if msg_sent.dt.tz is not None:
            msg_sent = msg_sent.dt.tz_localize(None)
            
        request_msgs = messages[
            (messages['user_id'] == user_id) & 
            (msg_sent <= req_date)
        ]
        
        msg_facts = {}
        for _, msg_row in request_msgs.iterrows():
            facts = self.msg_extractor.extract_facts(msg_row['message_id'], msg_row['message_text'])
            msg_facts.update(facts)
            
        img_facts = {}
        req_images = user_images[user_images['user_id'] == user_id]
        for _, img_row in req_images.iterrows():
            facts = self.img_interpreter.extract_image(img_row['image_id'], f"dataset/media/images/{img_row['image_id']}.png")
            if facts.get('document_type') == 'receipt' and facts.get('financial_amount', 0) > 100000:
                img_facts['suspension_end_date'] = (req_date + pd.Timedelta(days=90)).strftime('%Y-%m-%d')
                
        raw_facts = {**msg_facts, **img_facts}
        
        # Validate facts (Security Layer)
        overrides = self.fact_validator.validate_facts(user_id, raw_facts, req_date)
        
        # Separate historical settled and future pending/scheduled
        hist_start = req_date - timedelta(days=90)
        history = user_events[
            (user_events['settlement_date'] >= hist_start) & 
            (user_events['settlement_date'] < req_date) & 
            (user_events['status'] == 'settled')
        ].copy()
        
        # Ignore transactions that were refunded/reversed
        refunded_ids = history[history['direction'] == 'credit']['linked_event_id'].dropna().tolist()
        history = history[~history['event_id'].isin(refunded_ids)]
        
        # Ignore internal transfer duplicates
        history = history[~history['description'].str.contains('Internal transfer|transfer between your two accounts', case=False, na=False)]
        
        future = user_events[
            (user_events['settlement_date'] >= req_date) &
            (user_events['status'].isin(['pending', 'scheduled']))
        ].copy()
        
        base_profile = BaseProfile(
            user_id=user_id,
            current_balance=float(profile_row['current_available_balance']),
            minimum_balance=float(profile_row['minimum_balance_to_keep']),
            home_currency=home_currency
        )
        
        state = FinancialState(profile=base_profile, request_date=req_date.date())
        
        # Process pending debits
        pending_debits = future[(future['status'] == 'pending') & (future['direction'] == 'debit')]
        for _, r in pending_debits.iterrows():
            amt = self.cc.convert(r['amount'], r['currency'], home_currency, r['settlement_date'])
            state.pending_debits.append(amt)
            
        # Process scheduled events
        sched_events = future[future['status'] == 'scheduled']
        for _, r in sched_events.iterrows():
            amt = self.cc.convert(r['amount'], r['currency'], home_currency, r['settlement_date'])
            is_prepaid = False
            if r['event_id'] in image_facts and image_facts[r['event_id']].get('document_type') == 'receipt':
                is_prepaid = True
            state.scheduled_events.append(ScheduledEvent(
                event_id=r['event_id'],
                date=r['settlement_date'].date(),
                amount=amt,
                direction=r['direction'],
                category=r['category'],
                is_prepaid=is_prepaid
            ))
            
        # Process Recurring Income
        all_income_events = user_events[
            (user_events['direction'] == 'credit') & 
            (user_events['category'] == 'salary') &
            (user_events['status'] == 'settled')
        ].sort_values('settlement_date')
        
        if not overrides.get('salary_ended', False) and len(all_income_events) > 0:
            for desc in all_income_events['description'].unique():
                desc_lower = str(desc).lower()
                stream_events = all_income_events[all_income_events['description'] == desc].sort_values('settlement_date')
                
                # Always filter 'next confirmed' and 'final '
                if any(k in desc_lower for k in ['next confirmed', 'final ']):
                    continue
                    
                # For other one-time keywords (bonus, arrears, commission, etc.), 
                # only filter them if they are genuinely one-off (N=1).
                # If they occur multiple times, they are a recurring part of income.
                ONE_TIME_INCOME_KW = [
                    'arrears', 'bonus', 'commission', 'performance', 
                    'prize', 'promotion', 'prorated', 'one-time', 'one time'
                ]
                if len(stream_events) == 1 and any(k in desc_lower for k in ONE_TIME_INCOME_KW):
                    continue
                
                # Gig/platform payouts not projected when still variable/unclosed
                if any(k in desc_lower for k in ['app earnings', 'payout', 'platform']):
                    # Check if there are any pending messages related to this specific stream
                    should_drop = False
                    for m in request_msgs['message_text']:
                        msg_lower = str(m).lower()
                        if 'pending' in msg_lower or 'not withdrawable' in msg_lower:
                            # Try to match the stream to the message text (e.g. "weekly earnings" -> "Weekly app earnings")
                            if 'weekly' in msg_lower and 'weekly' in desc_lower:
                                should_drop = True
                            elif 'delivery' in msg_lower and 'delivery' in desc_lower:
                                should_drop = True
                            elif 'driver' in msg_lower and 'driver' in desc_lower:
                                should_drop = True
                            elif 'task' in msg_lower and 'task' in desc_lower:
                                should_drop = True
                    if should_drop:
                        continue
                
                # Skip streams with NaN amounts (can't project)
                valid_amounts = stream_events.dropna(subset=['amount'])
                if len(valid_amounts) == 0:
                    continue
                
                last_date = stream_events.iloc[-1]['settlement_date'].date()
                
                # Ignore stale salary streams that ended more than 45 days ago
                if (req_date.date() - last_date).days > 45:
                    continue
                    
                amounts = [self.cc.convert(r['amount'], r['currency'], home_currency, r['settlement_date']) for _, r in valid_amounts.iterrows()]
                # Use most recent amount as the projection (most representative of current salary)
                avg_amount = amounts[-1]
                
                diffs = stream_events['settlement_date'].diff().dt.days.dropna().tolist()
                avg_diff = float(np.mean(diffs)) if diffs else 30
                cadence = 7 if avg_diff < 10 else (14 if avg_diff < 18 else (21 if avg_diff < 25 else 30))
                
                next_d = advance_date(last_date, cadence)
                while next_d < req_date.date():
                    next_d = advance_date(next_d, cadence)
                    
                sal_override = overrides.get('salary_override')
                if sal_override and isinstance(sal_override, dict) and sal_override.get('amount') and float(sal_override.get('amount', 0)) > 0:
                    avg_amount = self.cc.convert(
                        float(sal_override['amount']),
                        sal_override.get('currency', home_currency),
                        home_currency,
                        req_date
                    )
                if overrides.get('salary_date_override'):
                    next_d = pd.to_datetime(overrides['salary_date_override']).date()
                    while next_d < req_date.date():
                        next_d = advance_date(next_d, cadence)
                        
                state.recurring_income.append(RecurringIncome(
                    category='salary',
                    amount=avg_amount,
                    cadence_days=cadence,
                    next_date=next_d
                ))
        
        # Process Recurring Expenses
        hist_debits = history[history['direction'] == 'debit']
        for cat in hist_debits['category'].unique():
            cat_events = hist_debits[hist_debits['category'] == cat].sort_values('settlement_date')
            if len(cat_events) < 2:
                continue
                
            most_recent = cat_events.iloc[-1]
            flexibility = most_recent['flexibility'] if pd.notna(most_recent['flexibility']) else 'fixed'
            
            min_allowed = 0.0
            if 'minimum_allowed_amount' in most_recent and pd.notna(most_recent['minimum_allowed_amount']):
                min_allowed = self.cc.convert(
                    float(most_recent['minimum_allowed_amount']),
                    most_recent['currency'],
                    home_currency,
                    most_recent['settlement_date']
                )
                
            diffs = cat_events['settlement_date'].diff().dt.days.dropna().tolist()
            avg_diff = float(np.mean(diffs)) if diffs else 30
            cadence = 7 if avg_diff < 10 else (14 if avg_diff < 18 else (21 if avg_diff < 25 else 30))
            
            last_date = cat_events.iloc[-1]['settlement_date'].date()
            next_d = advance_date(last_date, cadence)
            while next_d < req_date.date():
                next_d = advance_date(next_d, cadence)
                
            cat_copy = cat_events.copy()
            cat_copy['amount_home'] = cat_copy.apply(
                lambda r: self.cc.convert(r['amount'], r['currency'], home_currency, r['settlement_date']), axis=1
            )
            
            projected_amount = float(cat_copy['amount_home'].mean())
                
            if cat == 'rent' and overrides.get('rent_increase_pct'):
                projected_amount *= (1 + overrides['rent_increase_pct'])
                
            # Check prepaid suspension
            suspension_end = None
            for se in state.scheduled_events:
                if se.category == cat and se.is_prepaid:
                    months_covered = int(se.amount / projected_amount) if projected_amount > 0 else 0
                    if months_covered > 0:
                        suspension_end = se.date + timedelta(days=30 * months_covered)
                        
            state.recurring_expenses.append(RecurringExpense(
                category=cat,
                amount=projected_amount,
                cadence_days=cadence,
                next_date=next_d,
                flexibility=flexibility,
                min_allowed=min_allowed,
                suspension_end_date=suspension_end
            ))

        return state
