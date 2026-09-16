#!/usr/bin/env python3
"""Test datetime parsing."""

from datetime import datetime

ts = '2026-09-14T00:00:00.000+07:00'
print('Input:', ts)
parsed = datetime.fromisoformat(ts)
print('Parsed:', parsed)
print('Type:', type(parsed))
print('tzinfo:', parsed.tzinfo)

# The cutoff is naive datetime
cutoff = datetime(2026, 9, 13, 23, 59, 59)
print('Cutoff:', cutoff)

# Compare naive with aware - this will raise TypeError in Python 3
try:
    result = parsed >= cutoff
    print('ts >= cutoff:', result)
except TypeError as e:
    print('TypeError:', e)
    # Need to make both naive or both aware
    print('Making both aware...')
    from datetime import timezone, timedelta
    tz = timezone(timedelta(hours=7))
    cutoff_aware = cutoff.replace(tzinfo=tz)
    print('Cutoff aware:', cutoff_aware)
    print('ts >= cutoff_aware:', parsed >= cutoff_aware)