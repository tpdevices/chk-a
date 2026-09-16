#!/usr/bin/env python3
"""Create mock log data for 2026-09-14 (yesterday) for testing daily report."""

import json
from datetime import datetime, timedelta
import random

# Resolvers and FQDNs
resolvers = [
    "google", "cloudflare", "quad9", "OpenDNS", 
    "AdGuard DNS", "CleanBrowsing", "Comodo Secure DNS"
]
fqdns = ["www.egat.co.th", "api.github.com"]

# IP pools for each FQDN (simulating realistic DNS responses)
ip_pools = {
    "www.egat.co.th": [
        ["182.255.9.23"],
        ["182.255.9.24"],
        ["182.255.9.25"],
    ],
    "api.github.com": [
        ["20.205.243.168"],
        ["20.205.243.169"],
        ["140.82.121.4"],
    ],
}

# Simulate a day of checks (every ~5 minutes = ~288 cycles/day)
# For each cycle, each resolver queries each FQDN
# We'll make google mostly successful, others mixed

random.seed(42)  # Reproducible

records = []
base_date = datetime(2026, 9, 14, 0, 0, 0)  # 2026-09-14 00:00:00+07:00

for cycle in range(288):  # ~24 hours * 12 cycles/hour (every 5 min)
    cycle_time = base_date + timedelta(minutes=cycle * 5)
    
    for fqdn in fqdns:
        # Choose the "correct" IP for this FQDN (first in pool)
        correct_ips = ip_pools[fqdn][0]
        
        for resolver in resolvers:
            # Simulate different reliability per resolver
            if resolver == "google":
                success_rate = 0.98
            elif resolver in ["cloudflare", "quad9"]:
                success_rate = 0.85
            elif resolver in ["OpenDNS", "AdGuard DNS"]:
                success_rate = 0.70
            else:
                success_rate = 0.60
            
            success = random.random() < success_rate
            
            if success:
                # Sometimes return the correct IP, sometimes a different one from pool
                if random.random() < 0.9:
                    ips = correct_ips
                else:
                    ips = random.choice(ip_pools[fqdn])
                latency = random.uniform(40, 120)
                error = None
            else:
                ips = []
                latency = random.uniform(2000, 5000)
                error = random.choice(["TIMEOUT", "NXDOMAIN", "SERVFAIL", "REFUSED"])
            
            record = {
                "fqdn": fqdn,
                "resolver": resolver,
                "ips": ips,
                "latency_ms": round(latency, 2),
                "timestamp": cycle_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+07:00",
                "success": success,
                "error": error
            }
            records.append(record)

# Write to file
output_path = "/home/ipds/chk-a-test-data/checks_yesterday.jsonl"
import os
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, "w") as f:
    for record in records:
        f.write(json.dumps(record) + "\n")

print(f"Created {len(records)} records in {output_path}")
print(f"Date range: {base_date.strftime('%Y-%m-%d')} 00:00 to {(base_date + timedelta(days=1)).strftime('%Y-%m-%d')} 00:00")

# Print some stats
import pandas as pd
df = pd.DataFrame(records)
print(f"\nSuccess rates by resolver:")
for resolver in resolvers:
    rdf = df[df['resolver'] == resolver]
    print(f"  {resolver}: {rdf['success'].mean()*100:.1f}% ({rdf['success'].sum()}/{len(rdf)})")