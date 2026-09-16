#!/usr/bin/env python3
"""Test _load_recent_checks with real log file."""
import sys
sys.path.insert(0, '/opt/chk-a/src')
from chk_a.reporting.ml_insights import _load_recent_checks
from datetime import datetime, timezone, timedelta

# Test with real log file
log_path = '/var/log/chk-a/checks.jsonl'
ref = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone(timedelta(hours=7)))
df = _load_recent_checks(log_path, 1, reference_date=ref)
print(f'Loaded {len(df)} records')
print('Columns:', df.columns.tolist())
print('First 2 rows:')
print(df.head(2))
print('\nLast 2 rows:')
print(df.tail(2))