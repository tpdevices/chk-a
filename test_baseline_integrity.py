#!/usr/bin/env python3
"""Test script to verify baseline-based integrity computation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from chk_a.config.loader import load_config
from chk_a.agents.ml_agent import MLAgent
from chk_a.storage.baseline_store import BaselineStore
from chk_a.models.schemas import MLConfig

# Load config
config = load_config()
print(f"Config loaded: fqdns={len(config.fqdns)} resolvers={len(config.resolvers)}")

# Find the actual baseline file
baseline_paths = [
    Path(config.baseline_store_path),
    Path("/home/ipds/chk-a/data/baselines.json"),
    Path("/home/ipds/Hermes-Prj/chk-a/data/baselines.json"),
]

baseline_file = None
for p in baseline_paths:
    if p.exists():
        baseline_file = p
        break

if baseline_file is None:
    print("No baseline file found!")
    sys.exit(1)

print(f"\nUsing baseline file: {baseline_file}")

# Create ML components with correct baseline path
ml_config = config.ml
# SEC-002: BaselineStore validates path against CHK_A_BASELINE_DIR
# Temporarily override to allow loading from dev data dir for testing
import os
os.environ["CHK_A_BASELINE_DIR"] = "/home/ipds/chk-a/data"
baseline_store = BaselineStore(str(baseline_file))
ml_agent = MLAgent(ml_config, baseline_store)

print(f"All FQDNs in store: {baseline_store.all_fqdns()}")

# Check baselines for each FQDN
for fqdn_config in config.fqdns:
    fqdn = fqdn_config.name
    print(f"\n{'='*60}")
    print(f"FQDN: {fqdn}")
    print(f"{'='*60}")
    
    # Raw baseline
    raw = baseline_store.get_raw(fqdn)
    if raw:
        print(f"Raw baseline: {raw}")
        print(f"Sample count: {raw.get('sample_count', 0)}")
    else:
        print("No raw baseline found")
    
    # Normalized baseline
    baseline = baseline_store.get_baseline(fqdn)
    if baseline:
        print(f"Normalized baseline: {baseline}")
    else:
        print("No normalized baseline")

    # Get MLAgent counters
    counter = ml_agent._counters.get(fqdn)
    samples = ml_agent._samples.get(fqdn, 0)
    print(f"MLAgent counter: {dict(counter) if counter else 'empty'}")
    print(f"MLAgent samples: {samples}")

    # Test score with different observed IPs
    if baseline:
        # Test with same IPs as baseline (should score low = consistent)
        score_same = ml_agent.score(fqdn, list(baseline.keys()))
        print(f"Score vs baseline IPs {list(baseline.keys())}: {score_same:.4f} (lower = more consistent)")
        
        # Test with different IP (should score high = anomalous)
        test_diff_ip = "1.2.3.4"
        score_diff = ml_agent.score(fqdn, [test_diff_ip])
        print(f"Score vs different IP [{test_diff_ip}]: {score_diff:.4f} (higher = more anomalous)")

print("\nDone!")