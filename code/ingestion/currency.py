import pandas as pd
from datetime import timedelta
from collections import defaultdict, deque

class CurrencyConverter:
    def __init__(self, rates_df: pd.DataFrame):
        self.rates = rates_df.copy()
        self.rates['rate_date'] = pd.to_datetime(self.rates['rate_date'])
        
        # Precompute rate graph by date: date -> { (from, to): rate }
        self.date_graphs = defaultdict(dict)
        for _, row in self.rates.iterrows():
            d = row['rate_date'].strftime('%Y-%m-%d')
            f = str(row['from_currency']).strip().upper()
            t = str(row['to_currency']).strip().upper()
            r = float(row['rate'])
            if r > 0:
                self.date_graphs[d][(f, t)] = r
                self.date_graphs[d][(t, f)] = 1.0 / r

        self.all_dates = sorted(list(self.date_graphs.keys()))

    def _get_graph_for_date(self, date: pd.Timestamp) -> dict:
        date_str = date.strftime('%Y-%m-%d')
        if date_str in self.date_graphs:
            return self.date_graphs[date_str]
        
        # Find closest previous date, or fallback to closest overall
        date_ts = pd.to_datetime(date_str)
        prev_dates = [d for d in self.all_dates if pd.to_datetime(d) <= date_ts]
        if prev_dates:
            return self.date_graphs[prev_dates[-1]]
        elif self.all_dates:
            return self.date_graphs[self.all_dates[0]]
        return {}

    def get_conversion_rate(self, from_curr: str, to_curr: str, date: pd.Timestamp) -> float:
        f = str(from_curr).strip().upper()
        t = str(to_curr).strip().upper()
        if f == t:
            return 1.0
        
        graph = self._get_graph_for_date(date)
        if (f, t) in graph:
            return graph[(f, t)]
        
        # BFS search across currency exchange graph
        adj = defaultdict(dict)
        for (u, v), r in graph.items():
            adj[u][v] = r
            
        queue = deque([(f, 1.0)])
        visited = {f}
        while queue:
            curr, rate_so_far = queue.popleft()
            if curr == t:
                return rate_so_far
            for neighbor, edge_rate in adj[curr].items():
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, rate_so_far * edge_rate))
                    
        return 1.0

    def convert(self, amount: float, from_curr: str, to_curr: str, date: pd.Timestamp) -> float:
        if pd.isna(amount) or amount is None:
            return 0.0
        rate = self.get_conversion_rate(from_curr, to_curr, date)
        return float(amount) * rate
