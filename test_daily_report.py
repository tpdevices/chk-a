#!/usr/bin/env python3
"""Test script for daily report generation with writable output dir."""
import asyncio
import tempfile
from pathlib import Path
from chk_a.main import load_config
from chk_a.reporting.monthly_report import generate_daily_report

async def main():
    cfg = load_config('/etc/chk-a/config.yaml')
    
    # Override output_dir to writable location
    cfg.reporting.output_dir = "/home/ipds/test_reports"
    
    result = await generate_daily_report(cfg)
    print("Result:", result)
    
    # Check generated files
    output_dir = Path(cfg.reporting.output_dir)
    for f in output_dir.rglob("*"):
        if f.is_file():
            print(f"  {f}: {f.stat().st_size} bytes")

if __name__ == "__main__":
    asyncio.run(main())