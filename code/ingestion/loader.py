import pandas as pd
from typing import Dict

class DataLoader:
    def __init__(self, data_dir: str = 'dataset'):
        self.data_dir = data_dir
        self.cache: Dict[str, pd.DataFrame] = {}

    def _load(self, filename: str) -> pd.DataFrame:
        if filename not in self.cache:
            self.cache[filename] = pd.read_csv(f"{self.data_dir}/{filename}")
        return self.cache[filename]

    def get_profiles(self) -> pd.DataFrame:
        return self._load('financial_profiles.csv')

    def get_events(self) -> pd.DataFrame:
        df = self._load('financial_events.csv')
        # Convert date strings to datetime for easier comparison
        if not pd.api.types.is_datetime64_any_dtype(df['settlement_date']):
            df['settlement_date'] = pd.to_datetime(df['settlement_date'])
        if not pd.api.types.is_datetime64_any_dtype(df['event_date']):
            df['event_date'] = pd.to_datetime(df['event_date'])
        return df

    def get_messages(self) -> pd.DataFrame:
        return self._load('messages.csv')

    def get_images(self) -> pd.DataFrame:
        return self._load('images.csv')

    def get_rates(self) -> pd.DataFrame:
        return self._load('exchange_rates.csv')

    def get_requests(self) -> pd.DataFrame:
        df = self._load('sample_requests.csv')
        if not pd.api.types.is_datetime64_any_dtype(df['request_date']):
            df['request_date'] = pd.to_datetime(df['request_date'])
        return df

    def get_unseen_requests(self) -> pd.DataFrame:
        df = self._load('requests.csv')
        if not pd.api.types.is_datetime64_any_dtype(df['request_date']):
            df['request_date'] = pd.to_datetime(df['request_date'])
        return df

    def get_payment_options(self) -> pd.DataFrame:
        return self._load('request_payment_options.csv')
