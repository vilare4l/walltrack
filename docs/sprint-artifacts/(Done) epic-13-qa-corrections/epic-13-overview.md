# Epic 13: QA Corrections - Full Review & Testing

## Overview

This epic contains all corrections identified during the comprehensive QA review of Epics 10.5, 11, and 12. The review was conducted by the TEA (Test Architect) agent acting as Epic 13.

## Investigation Summary

### Areas Audited
1. **Postgres Migrations**: Two migration systems (001-020 old, V8-V14 new)
2. **Neo4j Clusters**: Relationship naming and sync issues
3. **API Routes**: Missing endpoints and registration issues
4. **Gradio UI**: Component integration and API path mismatches
5. **Code Review**: RiskManager/PositionSizer integration gaps

## Critical Issues Identified

| ID | Issue | Severity | Story |
|----|-------|----------|-------|
| C1 | Orders API route file missing | CRITICAL | 13-1 |
| C2 | Neo4j MEMBER_OF vs HAS_MEMBER mismatch | CRITICAL | 13-2 |
| C3 | Config API path mismatch (UI vs API) | CRITICAL | 13-3 |
| C4 | RiskManager stub not using PositionSizer | CRITICAL | 13-4 |
| C5 | Foreign key refs to walltrack.positions (doesn't exist) | CRITICAL | 13-5 |
| C6 | Position sizing router not registered | HIGH | 13-6 |

## High Priority Issues

| ID | Issue | Severity | Story |
|----|-------|----------|-------|
| H1 | Two config systems not unified | HIGH | 13-7 |
| H2 | Balance hardcoded to 10 SOL in pipeline | HIGH | 13-8 |
| H3 | exit_strategy_id hardcoded | HIGH | 13-8 |
| H4 | cluster_id not passed through signal chain | HIGH | 13-8 |
| H5 | Neo4j wallet sync one-directional | HIGH | 13-9 |

## Medium Priority Issues

| ID | Issue | Severity | Story |
|----|-------|----------|-------|
| M1 | French text in UI components | MEDIUM | 13-10 |
| M2 | Duplicate positions components | MEDIUM | 13-10 |
| M3 | Exit Simulation & What-If features to remove | MEDIUM | 13-11 |
| M4 | Signal scoring over-engineered (1,500 LOC, 15 criteria) | MEDIUM | 13-12 |
| M5 | Clustering is 100% manual, should be automatic on onboarding | MEDIUM | 13-13 |

## Story List

1. **Story 13-1**: Create Orders API Route
2. **Story 13-2**: Fix Neo4j Relationship Naming
3. **Story 13-3**: Fix Config API Path Mismatch
4. **Story 13-4**: Integrate PositionSizer into RiskManager
5. **Story 13-5**: Fix Postgres Schema References
6. **Story 13-6**: Register Missing API Routers
7. **Story 13-7**: Unify Config Systems
8. **Story 13-8**: Fix Signal Pipeline Hardcoded Values
9. **Story 13-9**: Add Neo4j Bidirectional Sync
10. **Story 13-10**: UI Polish & Cleanup
11. **Story 13-11**: Remove Exit Simulation & What-If Features
12. **Story 13-12**: Simplify Signal Scoring System
13. **Story 13-13**: Implement Recursive Clustering on Wallet Onboarding

## Implementation Order

1. **Phase A - Critical Blockers** (Stories 13-1 to 13-6)
   - Must be fixed for system to function end-to-end

2. **Phase B - Integration** (Stories 13-7 to 13-9)
   - Required for proper data flow

3. **Phase C - Polish** (Story 13-10)
   - UI cleanup and consistency

4. **Phase D - Simplification & Automation** (Stories 13-11, 13-12, 13-13)
   - Remove unused/complex features to reduce maintenance burden
   - Simplify scoring from 1,500 LOC to ~400 LOC
   - Automate clustering on wallet onboarding (recursive discovery)

## Testing Phase

After corrections:
1. Playwright E2E tests for Gradio UI
2. API integration tests
3. Neo4j cluster functionality tests
4. Webhook simulation tests

## Dependencies

- All V8-V14 migrations must be applied
- Neo4j database available
- Helius webhook configured

## Success Criteria

- All critical issues resolved
- E2E workflow from webhook to position creation works
- Config lifecycle works in UI
- Exit Simulation & What-If features cleanly removed
- No console errors in Gradio UI
- All tests pass after cleanup
