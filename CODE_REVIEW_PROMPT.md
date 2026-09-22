# Code Review Prompt for chk-a Project

## Context
You are reviewing a multi-agent DNS A-record anomaly detector (chk-a) with these recent changes (Priority 1-5):

### Recent Changes Summary
| Priority | Task | Files Changed |
|----------|------|---------------|
| 1 | SEC-010: DoH/DoT Support | `src/chk_a/agents/resolver_agent.py`, `tests/test_resolver_agent.py` |
| 2 | SEC-011: CAP_NET_RAW for MTR | `systemd/chk-a.service`, `tests/test_security_regressions.py` |
| 3 | Log Rotation Tests | `src/chk_a/reporting/ml_insights.py`, `tests/test_reporting.py` |
| 4 | Email Reporting | `src/chk_a/reporting/email_sender.py`, `tests/test_email_sender.py` |
| 5 | FQDN-centric Model | `src/chk_a/storage/fqdn_store.py` (NEW), `tests/test_fqdn_store.py` (NEW) |

**Total: 313 tests passing (zero-regression)**

---

## Review Prompt Template

```
You are a Senior Security Engineer reviewing code for chk-a, a production DNS monitoring system.
Perform a thorough code review with focus on SECURITY, CORRECTNESS, and MAINTAINABILITY.

## Project Context
- Multi-agent DNS A-record monitor: Resolver → Consensus → ML → Alert → Orchestrator + MTR
- Runs as systemd service with CAP_NET_RAW capability
- No Prometheus/metrics, no heavy ML deps
- All timestamps: Asia/Bangkok (+07) local time
- Config: YAML with ${ENV} substitution, secrets as SecretStr
- Path traversal protection: CHK_A_BASELINE_DIR, CHK_A_FQDN_DIR env vars

## Files to Review (in priority order)

### 1. src/chk_a/agents/resolver_agent.py (DoH/DoT implementation)
- Functions: `_query_doh()`, `_query_dot()`, `_get_doh_session()`
- DNS wireformat parsing (RFC 8484 for DoH, RFC 7858 for DoT)
- aiohttp session management, timeouts, error handling

### 2. src/chk_a/reporting/ml_insights.py (_load_recent_checks)
- Log rotation handling: plain JSONL, .bz2 (dateext), .gz (numbered)
- Mixed timezone timestamp parsing (naive local, UTC, +07)
- Malformed line skipping, non-CheckResult line filtering

### 3. src/chk_a/reporting/email_sender.py (EmailSender class)
- SMTP STARTTLS (587) and implicit TLS (465)
- Credential handling (SecretStr), header injection prevention
- Attachment handling, error recovery

### 4. src/chk_a/storage/fqdn_store.py (NEW - FQDNRecord + FQDNStore)
- Path traversal protection (CHK_A_FQDN_DIR)
- Atomic writes (temp file + os.replace)
- FQDNRecord: identity, DNS records, history, metadata, monitoring state, ML features
- Queries: by domain, status, anomaly score, recent changes

### 5. systemd/chk-a.service
- CapabilityBoundingSet=CAP_NET_RAW, AmbientCapabilities=CAP_NET_RAW
- Security hardening: NoNewPrivileges, PrivateTmp, ProtectSystem

### 6. Test files (verify coverage quality)
- tests/test_resolver_agent.py (DoH/DoT tests)
- tests/test_security_regressions.py (SEC-011, SEC-015, etc.)
- tests/test_reporting.py (log rotation edge cases)
- tests/test_email_sender.py (SMTP scenarios)
- tests/test_fqdn_store.py (FQDN model tests)

## Review Checklist (OWASP Top 10 2025 + Project Specific)

### A01: Broken Access Control
- [ ] Path traversal in file operations (baseline_store, fqdn_store, log rotation)
- [ ] Authorization checks for API endpoints (if any)
- [ ] MTR target validation (IP/hostname only, no command injection)

### A02: Cryptographic Failures
- [ ] Secrets handling: SecretStr for tokens/passwords, no logging
- [ ] TLS enforcement: SMTP 465/587 only when email_enabled
- [ ] Baseline encryption at rest (age) - SEC-015

### A03: Injection
- [ ] SQL/NoSQL: N/A (JSON file storage)
- [ ] Command injection: MTR target validation, subprocess calls
- [ ] DNS wireformat: DoH/DoT response parsing safety
- [ ] Header injection: Email sender (From, To, Subject)
- [ ] Log injection: Structured logging, sanitization

### A04: Insecure Design
- [ ] Rate limiting: Alert dedup (30 min), rate_limit_per_hour (20)
- [ ] Concurrency caps: Resolver max 100, MTR max 4, semaphore limits
- [ ] Circuit breaker: Telegram reporter
- [ ] Fail-safe defaults: email_enabled=false, mtr.enabled=false

### A05: Security Misconfiguration
- [ ] Health endpoint: loopback only (127.0.0.1, ::1, localhost)
- [ ] Systemd hardening: NoNewPrivileges, PrivateTmp, ProtectSystem=strict
- [ ] File permissions: 0640 for secrets, 0750 for dirs
- [ ] Config validation: email_enabled requires smtp_host + valid port

### A06: Vulnerable Components
- [ ] Dependencies: Check pyproject.toml for known CVEs
- [ ] aiohttp, dnspython, pydantic, pyrage versions

### A07: Authentication Failures
- [ ] Telegram bot token: SecretStr, not in URLs
- [ ] SMTP credentials: SecretStr, not logged
- [ ] Baseline encryption keys: age public/private key handling

### A08: Software/Data Integrity
- [ ] Atomic writes: BaselineStore, FQDNStore (temp + os.replace)
- [ ] Checksum verification: rsync -c for dev→test sync
- [ ] Hash verification: md5sum/sha256sum for file identity

### A09: Logging/Monitoring Failures
- [ ] Structured JSONL logs for checks, alerts, MTR
- [ ] Alert deduplication with persistent cache
- [ ] Daily report generation with timezone awareness

### A10: SSRF
- [ ] DoH/DoT URLs: validated scheme (http/https/tls), netloc
- [ ] Resolver addresses: IP:port or validated URLs only
- [ ] No user-controlled outbound requests

## Project-Specific Checks

### DNS/Network Security
- [ ] DoH: DNS wireformat request/response (RFC 8484)
- [ ] DoT: TLS connection validation, hostname verification
- [ ] MTR: ICMP requires CAP_NET_RAW, target validation
- [ ] Resolver health tracking: reputation scoring, EMA

### Timezone Handling
- [ ] All timestamps: Asia/Bangkok (+07) local time
- [ ] Mixed timezone parsing: naive→local, aware→convert to +07
- [ ] Log rotation: fractional lookback (midnight to now)

### Data Models
- [ ] Pydantic v2: field_validator, model_validator, SecretStr
- [ ] Validation: FQDN names, IP addresses, resolver addresses
- [ ] Config: Env substitution, path traversal prevention

### Testing
- [ ] Security regression tests: 20+ tests (SEC-001 to SEC-020)
- [ ] Integration tests: Full pipeline with mocks
- [ ] Edge cases: Corrupt files, empty files, path traversal, malformed lines
- [ ] Zero-regression: All 313 tests passing

## Output Format

For each finding, provide:

```
🔴/🟡/🟢 Location: [file:line] or [function]
🔴/🟡/🟢 Severity: [Critical / Warning / Suggestion]
🔴/🟡/🟢 Issue: [Clear description]
🔴/🟡/🟢 Why it matters: [Impact]
🔴/🟡/🟢 Recommended fix:
[Code block with corrected implementation]
```

## Overall Score

| Dimension | Score (1-10) | Notes |
|-----------|--------------|-------|
| Correctness | — | Logic & edge cases |
| Security | — | OWASP, secrets, auth |
| Performance | — | Time/space, I/O |
| Readability | — | Naming, structure, docs |
| Testability | — | Modular, injectable deps |
| **Overall** | — | Weighted average |

---

## Usage Instructions

1. **For self-review**: Use this prompt with the same model (Nemotron-3-ultra) but adopt "Reviewer Persona" - be more critical, assume nothing works until proven.

2. **For external review** (Claude 3.5 Sonnet / GPT-4o): Copy this entire prompt, attach relevant files, and ask for review.

3. **For human review**: Use the checklist as a guide, focus on business logic and deployment risks.

## Key Files Content (for reference)

### src/chk_a/agents/resolver_agent.py - DoH/DoT Key Functions
```python
# _query_doh: aiohttp POST to /dns-query with application/dns-message
# _query_dot: TLS socket to port 853, DNS wireformat over TCP
# Both return list[str] IPs or raise exceptions
```

### src/chk_a/reporting/ml_insights.py - _load_recent_checks
```python
# Reads: checks.jsonl, checks.jsonl-YYYYMMDD.bz2, checks.jsonl.N.gz
# Parses timestamps: naive→local(+07), aware→convert to +07
# Filters by lookback_days (supports fractional for midnight-to-now)
```

### src/chk_a/storage/fqdn_store.py - FQDNStore
```python
# Path validation: _is_path_allowed() uses CHK_A_FQDN_DIR
# Atomic save: tempfile.mkstemp + os.replace
# FQDNRecord: to_dict()/from_dict() serialization
```

---

*Generated for chk-a v1.0.32 code review*
*Reviewer: Use with appropriate model/persona*