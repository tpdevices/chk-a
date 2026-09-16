#!/usr/bin/env python3
"""Test rotated log loading for yesterday's data."""
import sys
sys.path.insert(0, '/opt/chk-a/src')
from chk_a.reporting.ml_insights import _load_recent_checks
from datetime import datetime, timezone, timedelta

# Test loading yesterday's data from rotated logs
# reference_date = today 2026-09-15, lookback=1 should get yesterday's data from rotated file
ref = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone(timedelta(hours=7)))
df = _load_recent_checks('/var/log/chk-a/checks.jsonl', 1, reference_date=ref)
print(f'Loaded {len(df)} records for yesterday (lookback=1 day)')
print('Date range:', df['timestamp'].min(), 'to', df['timestamp'].max())
print('Resolvers:', df['resolver'].unique().tolist())
print('Success rates:')
print(df.groupby('resolver')['success'].mean() * 100)