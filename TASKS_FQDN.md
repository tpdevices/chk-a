# FQDN Features Implementation Tasks

## Phase 1: Per-FQDN Custom Alert Thresholds
- [ ] 1. Extend FQDNConfig with alert_rules field (schemas.py)
- [ ] 2. Update orchestrator to use per-FQDN thresholds (_fqdn_config)
- [ ] 3. Update alert_agent to respect per-FQDN rules

## Phase 2: FQDN Availability Tracking
- [ ] 4. Add FQDN availability computation in orchestrator
- [ ] 5. Update FQDNStore with availability methods
- [ ] 6. Include availability in daily/monthly reports

## Phase 3: IP Change Detection/Alert
- [ ] 7. Add 'ip_change' to AnomalyEvent type literal
- [ ] 8. Implement IP change detection in _process_fqdn
- [ ] 9. Add ip_change alert type handling in alert_agent (Thai formatting)
- [ ] 10. Track IP changes in FQDNStore (already has add_ip_change)

## Phase 4: Tests
- [ ] 11. Test per-FQDN alert thresholds
- [ ] 12. Test IP change detection
- [ ] 13. Test FQDN availability metrics
