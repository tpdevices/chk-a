#!/usr/bin/env python3
"""Show example FQDN data structures."""

from chk_a.storage.fqdn_store import FQDNRecord
from datetime import datetime
import json

# Example 1: Simple FQDN with IP history
rec1 = FQDNRecord(
    fqdn="api.example.com",
    current_ips=["10.0.1.5", "10.0.1.6"],
    cname_chain=["api.example.com", "lb.example.com"],
    ttl=300,
    registrar="Cloudflare",
    expiry_date="2027-03-15",
    nameservers=["ns1.cloudflare.com", "ns2.cloudflare.com"],
    status="healthy",
    alert_rules={"anomaly_threshold": 0.7, "consensus_min_score": 0.8},
    baseline_ips={"10.0.1.5": 0.95, "10.0.1.6": 0.92},
    anomaly_score=0.05,
    flip_flop_count=0,
    geo_shifts=0,
)
rec1.add_ip_change(["10.0.1.5"], ["10.0.1.5", "10.0.1.6"], "consensus", datetime(2026, 9, 20, 14, 30))
rec1.add_ip_change(["10.0.1.4"], ["10.0.1.5"], "consensus", datetime(2026, 9, 15, 8, 15))
rec1.update_monitoring_state(True, 12.5, datetime(2026, 9, 23, 10, 0))

# Example 2: Complex FQDN with geo shift
rec2 = FQDNRecord(
    fqdn="cdn.service.co.th",
    current_ips=["203.0.113.10"],
    cname_chain=["cdn.service.co.th", "edge.cloudfront.net"],
    ttl=60,
    registrar="Amazon",
    expiry_date="2028-01-20",
    nameservers=["ns-123.awsdns-15.com", "ns-456.awsdns-56.net"],
    status="healthy",
    alert_rules={"anomaly_threshold": 0.5, "consensus_min_score": 0.6},
    baseline_ips={"203.0.113.10": 0.88, "198.51.100.20": 0.12},
    anomaly_score=0.25,
    flip_flop_count=3,
    geo_shifts=1,
)
rec2.add_ip_change(["198.51.100.20"], ["203.0.113.10"], "consensus", datetime(2026, 9, 10, 16, 45))
rec2.increment_flip_flop()
rec2.increment_flip_flop()
rec2.increment_flip_flop()
rec2.increment_geo_shift()
rec2.update_monitoring_state(True, 8.2, datetime(2026, 9, 23, 10, 0))

# Example 3: Degraded FQDN
rec3 = FQDNRecord(
    fqdn="internal-db.corp.local",
    current_ips=["192.168.10.50"],
    ttl=600,
    registrar="Internal",
    nameservers=["ns1.corp.local", "ns2.corp.local"],
    status="degraded",
    consecutive_failures=5,
    alert_rules={"anomaly_threshold": 0.8, "consensus_min_score": 0.9},
    baseline_ips={"192.168.10.50": 1.0},
    anomaly_score=0.65,
    flip_flop_count=0,
    geo_shifts=0,
)
rec3.update_monitoring_state(False, 0.0, datetime(2026, 9, 23, 9, 55))

examples = [
    ("Simple API FQDN", rec1),
    ("Thai CDN with geo shift", rec2),
    ("Internal DB (degraded)", rec3),
]

for title, rec in examples:
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print(f"{'='*60}")
    print(f"  FQDN:           {rec.fqdn}")
    print(f"  Domain:         {rec.domain}")
    print(f"  Subdomain:      {rec.subdomain or '(apex)'}")
    print(f"  Apex:           {rec.apex}")
    print(f"  Current IPs:    {rec.current_ips}")
    print(f"  CNAME Chain:    {rec.cname_chain or 'None'}")
    print(f"  TTL:            {rec.ttl}s")
    print(f"  Registrar:      {rec.registrar}")
    print(f"  Expiry:         {rec.expiry_date}")
    print(f"  Nameservers:    {rec.nameservers}")
    print(f"  Status:         {rec.status}")
    print(f"  Failures:       {rec.consecutive_failures}")
    print(f"  Last Checked:   {rec.last_checked}")
    print(f"  Alert Rules:    {rec.alert_rules}")
    print(f"  Baseline IPs:   {rec.baseline_ips}")
    print(f"  Anomaly Score:  {rec.anomaly_score:.2f}")
    print(f"  Flip-flop:      {rec.flip_flop_count}")
    print(f"  Geo Shifts:     {rec.geo_shifts}")
    print(f"  IP History ({len(rec.ip_history)} entries):")
    for h in rec.ip_history:
        print(f"    • {h['timestamp']} | {h['old_ips']} → {h['new_ips']} (source: {h['source']})")

# Show JSON serialization
print(f"\n{'='*60}")
print("📦 JSON Serialization (for storage)")
print(f"{'='*60}")
print(json.dumps(rec1.to_dict(), indent=2, ensure_ascii=False))