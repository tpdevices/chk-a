"""Machine-learning based reporting utilities for chk-a.

This module is responsible for analysing the historical check data (stored as
JSON-Lines in the log file defined by ``LoggingConfig.file``) and producing the
two ML-driven metrics required for the monthly report:

1. **Availability** – the proportion of successful resolver queries for each
   resolver over the configured look-back window.
2. **Integrity** – an anomaly score that reflects how *consistent* a resolver's
   answers are with respect to the learned baseline. Uses MLAgent.score()
   (total-variation distance against learned baseline) for robustness against
   mass-failure scenarios where Isolation Forest would flag healthy resolvers
   as anomalies.

The functions return plain Python data structures (dict / list) that can be
consumed by the graph generator, PDF generator and Telegram reporter.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from chk_a.agents.ml_agent import MLAgent
# ---------------------------------------------------------------------------
# Path Availability Analysis (ML-based)
# ---------------------------------------------------------------------------


def compute_path_availability(mtr_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Compute network path availability metrics from MTR data.

    Returns a dict keyed by resolver name with:
    - path_availability_pct (0-100): percentage of hops with < 10% loss
    - total_hops
    - healthy_hops (loss < 10%)
    - degraded_hops (loss 10-50%)
    - critical_hops (loss > 50%)
    - avg_latency_ms (last hop)
    - max_latency_ms (last hop)
    - bottleneck_hop: hop with highest loss
    - path_health_score: ML-based 0-100 score
    """
    if not mtr_data:
        return {}

    results = {}
    for resolver_name, trace in mtr_data.items():
        hops = trace.get("hops", [])
        if not hops:
            results[resolver_name] = {
                "path_availability_pct": 0.0,
                "total_hops": 0,
                "healthy_hops": 0,
                "degraded_hops": 0,
                "critical_hops": 0,
                "avg_latency_ms": 0.0,
                "max_latency_ms": 0.0,
                "bottleneck_hop": None,
                "path_health_score": 0.0,
            }
            continue

        total = len(hops)
        healthy = sum(1 for h in hops if h.get("loss_pct", 0) < 10)
        degraded = sum(1 for h in hops if 10 <= h.get("loss_pct", 0) < 50)
        critical = sum(1 for h in hops if h.get("loss_pct", 0) >= 50)

        path_availability = (healthy / total * 100) if total > 0 else 0.0

        # Last hop latency (destination)
        last_hop = hops[-1] if hops else {}
        avg_latency = last_hop.get("avg_ms", 0.0)
        max_latency = last_hop.get("worst_ms", 0.0)

        # Bottleneck hop (highest loss)
        bottleneck = max(hops, key=lambda h: h.get("loss_pct", 0), default=None)

        # Build features for ML-based path health scoring
        features = _build_path_features(hops)

        results[resolver_name] = {
            "path_availability_pct": round(path_availability, 2),
            "total_hops": total,
            "healthy_hops": healthy,
            "degraded_hops": degraded,
            "critical_hops": critical,
            "avg_latency_ms": round(avg_latency, 2),
            "max_latency_ms": round(max_latency, 2),
            "bottleneck_hop": bottleneck,
            "raw_features": features,
        }

    # Compute ML-based path health scores across all resolvers
    if results:
        _score_path_health(results)

    return results


def _build_path_features(hops: list[dict]) -> dict[str, float]:
    """Build feature vector for path health ML scoring."""
    if not hops:
        return {}

    losses = [h.get("loss_pct", 0) for h in hops]
    latencies = [h.get("avg_ms", 0) for h in hops if h.get("avg_ms", 0) > 0]
    stdevs = [h.get("stdev_ms", 0) for h in hops if h.get("stdev_ms", 0) > 0]

    # Loss statistics
    max_loss = max(losses) if losses else 0
    avg_loss = np.mean(losses) if losses else 0
    loss_std = np.std(losses) if len(losses) > 1 else 0

    # Latency statistics
    avg_latency = np.mean(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    latency_std = np.std(latencies) if len(latencies) > 1 else 0

    # Jitter (avg stdev)
    avg_jitter = np.mean(stdevs) if stdevs else 0

    # Hop count
    hop_count = len(hops)

    # Critical hop indicators
    critical_hops = sum(1 for loss in losses if loss >= 50)
    degraded_hops = sum(1 for loss in losses if 10 <= loss < 50)

    return {
        "max_loss_pct": max_loss,
        "avg_loss_pct": avg_loss,
        "loss_std": loss_std,
        "avg_latency_ms": avg_latency,
        "max_latency_ms": max_latency,
        "latency_std": latency_std,
        "avg_jitter_ms": avg_jitter,
        "hop_count": hop_count,
        "critical_hops": critical_hops,
        "degraded_hops": degraded_hops,
    }


def _score_path_health(path_results: dict[str, dict[str, Any]]) -> None:
    """Compute ML-based path health scores using Isolation Forest."""
    # Extract features
    resolver_names = list(path_results.keys())
    feature_rows = []
    feature_names = None

    for resolver, data in path_results.items():
        features = data.get("raw_features", {})
        if not features:
            feature_rows.append([0.0] * 10)
            continue
        if feature_names is None:
            feature_names = list(features.keys())
        row = [features.get(name, 0.0) for name in feature_names]
        feature_rows.append(row)

    if not feature_rows or feature_names is None:
        for resolver in resolver_names:
            path_results[resolver]["path_health_score"] = 50.0
        return

    X = np.array(feature_rows)

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Isolation Forest for anomaly detection on path features
    # contamination='auto' for small datasets
    iso = IsolationForest(contamination="auto", random_state=42, n_estimators=200)
    iso.fit(X_scaled)

    decision_scores = iso.decision_function(X_scaled)
    min_score, max_score = decision_scores.min(), decision_scores.max()
    if max_score > min_score:
        health_scores = (decision_scores - min_score) / (max_score - min_score) * 100
    else:
        health_scores = np.full_like(decision_scores, 50.0)

    for i, resolver in enumerate(resolver_names):
        path_results[resolver]["path_health_score"] = round(float(health_scores[i]), 2)


# ---------------------------------------------------------------------------
# MTR data collection
# ---------------------------------------------------------------------------


def _load_mtr_data(mtr_log_path: str, lookback_days: float) -> dict[str, Any]:
    """Load MTR results from JSON log file.

    MTR results are stored as JSONL with one MTRResult per line.
    """
    if not mtr_log_path or not Path(mtr_log_path).is_file():
        return {}

    cutoff = datetime.now() - timedelta(days=lookback_days)
    mtr_results: dict[str, list[dict]] = {}

    with Path(mtr_log_path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                ts = datetime.fromisoformat(rec.get("timestamp", ""))
                if ts >= cutoff:
                    resolver = rec.get("resolver_name", "unknown")
                    if resolver not in mtr_results:
                        mtr_results[resolver] = []
                    mtr_results[resolver].append(rec)
            except Exception as exc:
                log.debug("Skipping malformed MTR log line: %s (%s)", line, exc)

    # For each resolver, keep the most recent successful trace
    result = {}
    for resolver, traces in mtr_results.items():
        successful_traces = [t for t in traces if t.get("success", False)]
        if successful_traces:
            # Use the most recent trace
            latest = max(successful_traces, key=lambda x: x.get("timestamp", ""))
            result[resolver] = latest

    return result


# ---------------------------------------------------------------------------
# Helper: load recent check results from the JSON-Lines log file
# ---------------------------------------------------------------------------


def _load_recent_checks(
    log_path: str,
    lookback_days: float,
    reference_date: datetime | None = None,
    start_date: datetime | None = None,
) -> pd.DataFrame:
    """Load check results from ``log_path`` that fall within the last *lookback_days*.

    The log file is written by ``utils.logger`` in JSON-Lines format, each line
    containing the fields defined in :class:`chk_a.models.schemas.CheckResult`.
    Missing or malformed lines are ignored but logged at DEBUG level.

    Args:
        log_path: Path to the JSONL log file.
        lookback_days: Number of days to look back from reference_date (can be fractional).
        reference_date: Reference datetime for the lookback window. Defaults to now (Asia/Bangkok).
    """
    if reference_date is None:
        reference_date = datetime.now()

    # Handle timezone: log timestamps may or may not have timezone info.
    # Make reference_date timezone-aware if it's naive, using Asia/Bangkok +07.
    from datetime import timezone, timedelta
    default_tz = timezone(timedelta(hours=7))  # Asia/Bangkok
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=default_tz)

    cutoff = reference_date - timedelta(days=lookback_days)
    log.debug("_load_recent_checks: reference_date=%s, lookback_days=%s, cutoff=%s",
              reference_date.isoformat(), lookback_days, cutoff.isoformat())
    records: list[dict] = []
    path = Path(log_path)

    # Determine log directory and base filename for rotated files
    log_dir = path.parent
    log_name = path.name  # e.g., "checks.jsonl"

    # Collect all log files to read: current + rotated files within lookback window
    log_files = []

    # 1. Current log file
    if path.is_file():
        log_files.append((path, "r", None))  # (path, mode, opener)

    # 2. Rotated files with dateext pattern: checks.jsonl-YYYYMMDD.bz2 or .gz
    #    and numbered backups: checks.jsonl.1.gz, checks.jsonl.2.gz, etc.
    if log_dir.is_dir():
        for rotated_path in log_dir.iterdir():
            if rotated_path.name == log_name:
                continue  # skip current log

            # Check if it's a rotated version of our log file
            if not rotated_path.name.startswith(log_name + "-") and not rotated_path.name.startswith(log_name + "."):
                continue

            # Determine opener based on extension
            opener = None
            mode = "r"
            if rotated_path.suffix == ".bz2":
                import bz2
                opener = bz2.open
                mode = "rt"
            elif rotated_path.suffix == ".gz":
                import gzip
                opener = gzip.open
                mode = "rt"

            # For dateext files (checks.jsonl-YYYYMMDD.bz2), extract date and check if in range
            if rotated_path.name.startswith(log_name + "-"):
                # Try to extract date from filename: checks.jsonl-20260914.bz2
                date_str = rotated_path.name[len(log_name) + 1:-len(rotated_path.suffix)]  # remove .bz2/.gz
                if len(date_str) == 8 and date_str.isdigit():
                    try:
                        file_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=default_tz)
                        # File contains logs for this date; check if it overlaps with lookback window
                        # The file covers the full day, so check if file_date >= cutoff.date()
                        if file_date.date() >= cutoff.date():
                            log_files.append((rotated_path, mode, opener))
                    except ValueError:
                        pass  # Not a dateext file, skip date check
                else:
                    # Not a standard dateext, include it anyway (will be filtered by timestamp)
                    log_files.append((rotated_path, mode, opener))
            else:
                # Numbered backup (checks.jsonl.1.gz, etc.) - include and filter by timestamp
                log_files.append((rotated_path, mode, opener))

    # Sort files by modification time (newest first) for consistent processing
    log_files.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)

    # Process all collected log files
    for file_path, mode, opener in log_files:
        if not file_path.is_file():
            continue
        try:
            if opener:
                fh = opener(file_path, mode, encoding="utf-8")
            else:
                fh = file_path.open(mode, encoding="utf-8")

            with fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        # Only keep actual CheckResult records (have fqdn, resolver, success fields)
                        # Skip log messages (cycle complete, next cycle, etc.)
                        if not ("fqdn" in rec and "resolver" in rec and "success" in rec):
                            continue
                        ts_str = rec.get("timestamp", "")
                        ts = datetime.fromisoformat(ts_str)
                        # Handle timezone comparison: log timestamps are in Asia/Bangkok local time (naive or aware).
                        # Ensure both are timezone-aware in the same timezone for comparison.
                        compare_ts = ts
                        if compare_ts.tzinfo is None:
                            # Log timestamps are stored in local time (Asia/Bangkok) without tzinfo
                            compare_ts = compare_ts.replace(tzinfo=default_tz)
                        elif compare_ts.tzinfo != cutoff.tzinfo:
                            # Convert to cutoff's timezone if different
                            compare_ts = compare_ts.astimezone(cutoff.tzinfo)

                        log.debug("  record ts=%s, compare_ts=%s, cutoff=%s, include=%s",
                                  ts.isoformat(), compare_ts.isoformat(), cutoff.isoformat(), compare_ts >= cutoff)

                        if compare_ts >= cutoff:
                            records.append(rec)
                    except Exception as exc:  # pragma: no cover - defensive
                        log.debug("Skipping malformed log line in %s: %s (%s)", file_path.name, line, exc)
        except Exception as exc:
            log.warning("Failed to read rotated log file %s: %s", file_path.name, exc)

    if not records:
        return pd.DataFrame()
    # Parse timestamps individually to handle mixed timezones (naive + aware)
    # Naive timestamps are stored in local time (Asia/Bangkok)
    # Timezone-aware timestamps should be converted to Asia/Bangkok
    for rec in records:
        ts_str = rec.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                # Naive timestamp - assume it's already in local time (Asia/Bangkok)
                ts = ts.replace(tzinfo=default_tz)
            else:
                # Timezone-aware - convert to Asia/Bangkok
                ts = ts.astimezone(default_tz)
            rec["timestamp"] = ts
        except Exception:
            # If parsing fails, use reference_date as fallback
            rec["timestamp"] = reference_date
    df = pd.DataFrame(records)
    log.debug("_load_recent_checks: loaded %d records, time range %s to %s",
              len(df), df["timestamp"].min(), df["timestamp"].max())
    return df


# ---------------------------------------------------------------------------
# Availability analysis
# ---------------------------------------------------------------------------


def compute_availability(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Compute per-resolver availability metrics.

    Returns a dict keyed by resolver name with:
    - total_queries
    - successful_queries
    - failed_queries
    - availability_pct (0-100)
    - avg_latency_ms (successful only)
    - median_latency_ms
    - p95_latency_ms
    - p99_latency_ms
    - hourly_availability (dict hour->pct)
    - daily_availability (dict date->pct)  # NEW: for daily heatmap
    """
    if df.empty:
        return {}

    results: dict[str, dict[str, Any]] = {}
    for resolver, group in df.groupby("resolver"):
        total = len(group)
        successful = group[group["success"]]
        failed = group[~group["success"]]
        success_count = len(successful)
        fail_count = len(failed)

        availability = (success_count / total * 100) if total > 0 else 0.0

        latency_stats = {}
        if success_count > 0:
            latencies = successful["latency_ms"].values
            latency_stats = {
                "avg_latency_ms": float(np.mean(latencies)),
                "median_latency_ms": float(np.median(latencies)),
                "p95_latency_ms": float(np.percentile(latencies, 95)),
                "p99_latency_ms": float(np.percentile(latencies, 99)),
                "min_latency_ms": float(np.min(latencies)),
                "max_latency_ms": float(np.max(latencies)),
            }

        # Hourly availability
        hourly = {}
        for hour in range(24):
            hour_group = group[group["timestamp"].dt.hour == hour]
            if len(hour_group) > 0:
                hour_success = len(hour_group[hour_group["success"]])
                hourly[hour] = hour_success / len(hour_group) * 100
            else:
                hourly[hour] = None

        # Daily availability (NEW) - for daily heatmap in monthly report
        daily = {}
        if not group.empty:
            # Group by date (normalize timestamp to date)
            group_copy = group.copy()
            group_copy["date"] = group_copy["timestamp"].dt.date
            for date, date_group in group_copy.groupby("date"):
                date_success = len(date_group[date_group["success"]])
                daily[str(date)] = date_success / len(date_group) * 100

        results[resolver] = {
            "total_queries": total,
            "successful_queries": success_count,
            "failed_queries": fail_count,
            "availability_pct": round(availability, 2),
            **latency_stats,
            "hourly_availability": hourly,
            "daily_availability": daily,  # NEW
        }

    return results


# ---------------------------------------------------------------------------
# Integrity analysis (baseline-based, replaces Isolation Forest)
# ---------------------------------------------------------------------------


def _build_integrity_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Build feature matrix for integrity anomaly detection.

    Features per resolver:
    - success_rate
    - avg_latency
    - latency_std
    - unique_ip_count (diversity of answers)
    - ip_stability (how often the same IP set appears)
    - error_rate
    - nxdomain_rate
    """
    if df.empty:
        return pd.DataFrame(), []

    features_list = []
    resolver_names = []

    for resolver, group in df.groupby("resolver"):
        total = len(group)
        successful = group[group["success"]]
        failed = group[~group["success"]]

        success_rate = len(successful) / total if total > 0 else 0.0
        error_rate = len(failed) / total if total > 0 else 0.0

        # Latency stats
        if len(successful) > 0:
            latencies = successful["latency_ms"].values
            avg_latency = float(np.mean(latencies))
            latency_std = float(np.std(latencies)) if len(latencies) > 1 else 0.0
        else:
            avg_latency = 0.0
            latency_std = 0.0

        # IP diversity - count unique IP sets returned
        ip_sets = []
        for _, row in successful.iterrows():
            ips = tuple(sorted(row.get("ips", [])))
            ip_sets.append(ips)
        unique_ip_count = len(set(ip_sets))

        # IP stability - most common IP set frequency
        if ip_sets:
            from collections import Counter

            ip_counter = Counter(ip_sets)
            most_common_freq = ip_counter.most_common(1)[0][1]
            ip_stability = most_common_freq / len(ip_sets)
        else:
            ip_stability = 0.0

        # NXDOMAIN rate (error contains NXDOMAIN)
        nxdomain_count = sum(
            1 for _, row in failed.iterrows() if "NXDOMAIN" in str(row.get("error", "")).upper()
        )
        nxdomain_rate = nxdomain_count / total if total > 0 else 0.0

        features_list.append(
            [
                success_rate,
                avg_latency,
                latency_std,
                unique_ip_count,
                ip_stability,
                error_rate,
                nxdomain_rate,
            ]
        )
        resolver_names.append(resolver)

    feature_names = [
        "success_rate",
        "avg_latency",
        "latency_std",
        "unique_ip_count",
        "ip_stability",
        "error_rate",
        "nxdomain_rate",
    ]

    return pd.DataFrame(features_list, columns=feature_names, index=resolver_names), resolver_names


def compute_integrity(
    df: pd.DataFrame,
    ml_agent: "MLAgent | None" = None,
) -> dict[str, dict[str, Any]]:
    """Compute per-resolver integrity scores.

    Uses baseline-based scoring via MLAgent.score() when an ml_agent is provided.
    Raises ValueError if ml_agent is None (Isolation Forest fallback removed
    due to false positives during mass-failure events).

    Returns a dict keyed by resolver name with:
    - integrity_score (0-100, higher = more consistent with baseline)
    - anomaly_score (0-1, lower = more consistent)
    - is_anomaly (bool, True if integrity < 50 or success_rate == 0)
    - success_rate (0-100)
    - total_queries (int)
    - raw_features (dict)
    """
    if df.empty:
        return {}

    # Use baseline-based integrity - ml_agent is required
    if ml_agent is not None:
        return _compute_integrity_baseline_based(df, ml_agent)

    # Isolation Forest fallback removed (false positives during mass failures)
    raise ValueError(
        "ml_agent is required for integrity computation. "
        "Isolation Forest fallback removed due to false anomalies during mass-failure events."
    )


def _compute_integrity_baseline_based(
    df: pd.DataFrame,
    ml_agent: MLAgent,
) -> dict[str, dict[str, Any]]:
    """Compute per-resolver integrity using baseline-based MLAgent.score().

    Uses MLAgent.score() (total-variation distance against learned baseline)
    instead of Isolation Forest. This avoids false anomalies when multiple
    resolvers fail simultaneously (e.g., network outage) — only resolvers
    whose observed IPs deviate from the learned baseline are flagged.

    Returns a dict keyed by resolver name with:
    - integrity_score (0-100, higher = more consistent with baseline)
    - anomaly_score (0-1, inverse of integrity)
    - is_anomaly (bool, True if integrity < 50 or success_rate == 0)
    - success_rate (0-100)
    - total_queries (int)
    - raw_features (dict)
    """
    results = {}

    for resolver, group in df.groupby("resolver"):
        total_queries = len(group)
        successful = group[group["success"]]
        success_rate = len(successful) / total_queries if total_queries > 0 else 0.0

        # For each FQDN, check how consistent the resolver is with baseline
        fqdn_scores = []
        # Also collect IP stability/diversity metrics
        all_observed_ips = []
        ip_sets = []
        for fqdn, fqdn_group in group.groupby("fqdn"):
            successful_fqdn = fqdn_group[fqdn_group["success"]]
            if len(successful_fqdn) == 0:
                # All queries for this FQDN failed - score as anomaly
                fqdn_scores.append(1.0)  # anomaly_score = 1.0 (fully anomalous)
                continue

            # Get the most recent IPs from this resolver for this FQDN
            latest_result = successful_fqdn.iloc[-1]
            observed_ips = list(latest_result.get("ips", []))
            all_observed_ips.extend(observed_ips)
            ip_sets.append(tuple(sorted(observed_ips)))

            # Score against baseline using MLAgent
            # score() returns 0.0 (=consistent) to 1.0 (=anomalous)
            anomaly_score = ml_agent.score(str(fqdn), observed_ips)
            fqdn_scores.append(anomaly_score)

        # Average anomaly score across all FQDNs for this resolver
        avg_anomaly_score = sum(fqdn_scores) / len(fqdn_scores) if fqdn_scores else 1.0
        # Convert to integrity: 0 (anomalous) -> 100 (consistent)
        integrity = (1.0 - avg_anomaly_score) * 100.0

        # Calculate IP stability & diversity (same as Isolation Forest method)
        unique_ip_count = len(set(all_observed_ips))
        if ip_sets:
            from collections import Counter
            ip_set_counter = Counter(ip_sets)
            most_common_freq = max(ip_set_counter.values())
            ip_stability = most_common_freq / len(ip_sets)
        else:
            ip_stability = 0.0

        # If resolver is consistently failing, that's an integrity issue
        if success_rate == 0.0:
            integrity = 0.0
            is_anomaly = True
        else:
            is_anomaly = integrity < 50.0

        results[resolver] = {
            "integrity_score": round(integrity, 2),
            "anomaly_score": round(avg_anomaly_score, 4),
            "is_anomaly": is_anomaly,
            "success_rate": round(success_rate * 100, 2),
            "total_queries": total_queries,
            "raw_features": {
                "success_rate": round(success_rate, 4),
                "avg_anomaly_score": round(avg_anomaly_score, 4),
                "fqdn_count": len(fqdn_scores),
                "unique_ip_count": unique_ip_count,
                "ip_stability": round(ip_stability, 4),
            },
        }

    return results


def _compute_integrity_isolation_forest(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Compute per-resolver integrity using Isolation Forest (legacy method).

    Returns a dict keyed by resolver name with:
    - integrity_score (0-100, higher = more consistent/normal)
    - anomaly_score (raw IsolationForest score, lower = more anomalous)
    - is_anomaly (bool)
    - feature_contributions (which features drove the anomaly)
    """
    features_df, resolver_names = _build_integrity_features(df)
    if features_df.empty:
        return {}

    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features_df.values)
    # Isolation Forest for anomaly detection
    # contamination='auto' lets the model decide
    iso = IsolationForest(contamination="auto", random_state=42, n_estimators=200)
    iso.fit(X_scaled)
    # Decision function: higher = more normal, lower = more anomalous
    # Convert to 0-100 integrity score
    decision_scores = iso.decision_function(X_scaled)
    # Normalize to 0-100 (typical range is roughly -0.5 to 0.5)
    min_score, max_score = decision_scores.min(), decision_scores.max()
    if max_score > min_score:
        integrity_scores = (decision_scores - min_score) / (max_score - min_score) * 100
    else:
        integrity_scores = np.full_like(decision_scores, 50.0)

    # Anomaly predictions
    preds = iso.predict(X_scaled)  # 1 = normal, -1 = anomaly

    results = {}
    for i, resolver in enumerate(resolver_names):
        # Feature contributions (approximate via feature importance on single sample)
        # We compute how much each feature deviates from the mean
        feature_vals = features_df.iloc[i].values
        feature_means = features_df.mean().values
        feature_stds = np.array(features_df.std().values.copy())  # ensure mutable array
        feature_stds[feature_stds == 0] = 1.0  # avoid div by zero
        z_scores = np.abs((feature_vals - feature_means) / feature_stds)
        # Top contributing features
        top_features = sorted(zip(features_df.columns, z_scores), key=lambda x: x[1], reverse=True)[
            :3
        ]

        results[resolver] = {
            "integrity_score": round(float(integrity_scores[i]), 2),
            "anomaly_score": round(float(decision_scores[i]), 4),
            "is_anomaly": bool(preds[i] == -1),
            "top_contributing_features": [
                {"feature": f, "z_score": round(float(z), 2)} for f, z in top_features
            ],
            "raw_features": features_df.iloc[i].to_dict(),
        }

    return results


# ---------------------------------------------------------------------------#
# Public API
# ---------------------------------------------------------------------------#


def generate_ml_insights(
    log_path: str,
    lookback_days: float = 30.0,
    mtr_log_path: str = "",
    ml_agent: "MLAgent | None" = None,
    reference_date: datetime | None = None,
    start_date: datetime | None = None,
) -> dict[str, Any]:
    """Generate complete ML insights for the monthly report.

    Returns:
        {
            "availability": {resolver: {...}},
            "integrity": {resolver: {...}},
            "path_availability": {resolver: {...}},  # Path availability with ML health scores
            "mtr": {resolver: {...}},  # MTR path data for visualization
            "summary": {
                "total_resolvers": int,
                "total_queries": int,
                "overall_availability_pct": float,
                "anomalous_resolvers": list[str],
                "best_resolver": str,
                "worst_resolver": str,
            },
            "generated_at": str (ISO format),
            "lookback_days": int,
        }
    """
    df = _load_recent_checks(log_path, float(lookback_days), reference_date=reference_date, start_date=start_date)

    # Load MTR data if path provided
    mtr_data = {}
    path_availability = {}
    if mtr_log_path:
        mtr_data = _load_mtr_data(mtr_log_path, lookback_days)
        path_availability = compute_path_availability(mtr_data)

    if df.empty:
        log.warning("No check data available for ML insights")
        return {
            "availability": {},
            "integrity": {},
            "path_availability": path_availability,
            "mtr": mtr_data,
            "summary": {
                "total_resolvers": 0,
                "total_queries": 0,
                "overall_availability_pct": 0.0,
                "anomalous_resolvers": [],
                "best_resolver": "",
                "worst_resolver": "",
            },
            "generated_at": datetime.now().isoformat(),
            "lookback_days": lookback_days,
        }

    availability = compute_availability(df)
    integrity = compute_integrity(df, ml_agent=ml_agent)

    # Summary statistics
    total_queries = len(df)
    total_resolvers = len(availability)
    overall_availability = (
        sum(v["availability_pct"] for v in availability.values()) / total_resolvers
        if total_resolvers > 0
        else 0.0
    )
    # Overall integrity average
    overall_integrity = (
        sum(v["integrity_score"] for v in integrity.values()) / total_resolvers
        if total_resolvers > 0
        else 0.0
    )
    anomalous = [r for r, v in integrity.items() if v.get("is_anomaly", False)]

    # Best/worst by availability
    if availability:
        best = max(availability.items(), key=lambda x: x[1]["availability_pct"])[0]
        worst = min(availability.items(), key=lambda x: x[1]["availability_pct"])[0]
    else:
        best = worst = ""

    return {
        "availability": availability,
        "integrity": integrity,
        "path_availability": path_availability,
        "mtr": mtr_data,
        "summary": {
            "total_resolvers": total_resolvers,
            "total_queries": total_queries,
            "overall_availability_pct": round(overall_availability, 2),
            "overall_integrity_pct": round(overall_integrity, 2),
            "anomalous_resolvers": anomalous,
            "best_resolver": best,
            "worst_resolver": worst,
        },
        "generated_at": datetime.now().isoformat(),
        "lookback_days": lookback_days,
    }
