# WallTrack E2E Test Specifications

> **Version:** 1.0
> **Epic:** 14 - Simplification
> **Target:** Playwright + Gradio Dashboard
> **Author:** Murat (TEA Agent)

---

## Overview

This directory contains executable E2E test specifications for WallTrack. Each spec covers a specific functional area with:

- Test case definitions (TC-XX.X)
- Playwright locator requirements
- Test data prerequisites
- Estimated execution time

---

## Spec Index

| Spec | File | Priority | Risk | Est. Time |
|------|------|----------|------|-----------|
| 01 | [Dashboard Navigation](01-dashboard-navigation.md) | P1 | Low | 15s |
| 02 | [Token Discovery](02-token-discovery.md) | P1 | Medium | 40s |
| 03 | [Wallet Management](03-wallet-management.md) | P1 | Medium | 35s |
| 04 | [Cluster Visualization](04-cluster-visualization.md) | P1 | Medium | 21s |
| 05 | [Signal Scoring](05-signal-scoring.md) | P0 | Critical | 30s |
| 06 | [Position Management](06-positions.md) | P0 | Critical | 40s |
| 07 | [Order Management](07-orders.md) | P0 | Critical | 30s |
| 08 | [Configuration Panel](08-configuration.md) | P2 | Low | 35s |
| 09 | [Webhooks](09-webhooks.md) | P0 | Critical | 30s |
| 10 | [Simulation Mode](10-simulation-mode.md) | P1 | Medium | 25s |

**Total Estimated Time:** ~5 minutes

---

## Execution Priority

### P0 - Critical Path (Must Pass)

Execute first - core trading functionality:

```bash
pytest tests/e2e/ -k "signal or position or order or webhook" -v
```

1. **Spec 09: Webhooks** - Signal ingestion point
2. **Spec 05: Signal Scoring** - Trade decisions
3. **Spec 06: Positions** - Position lifecycle
4. **Spec 07: Orders** - Order execution

### P1 - High Priority

Execute second - discovery and core features:

```bash
pytest tests/e2e/ -k "discovery or wallet or cluster or navigation or simulation" -v
```

5. **Spec 01: Dashboard Navigation** - Basic UI verification
6. **Spec 02: Token Discovery** - Discovery pipeline
7. **Spec 03: Wallet Management** - Watchlist operations
8. **Spec 04: Clusters** - Cluster visualization
9. **Spec 10: Simulation Mode** - Mode management

### P2 - Normal Priority

Execute last - configuration:

```bash
pytest tests/e2e/ -k "config" -v
```

10. **Spec 08: Configuration** - Scoring parameters

---

## Test Environment Setup

### Prerequisites

```bash
# 1. Start backend services
docker compose up -d

# 2. Start Gradio dashboard
uv run python -m walltrack.ui.dashboard

# 3. Verify services
curl http://localhost:8000/health  # API
curl http://localhost:7865         # Gradio
```

### Environment Variables

```env
GRADIO_HOST=localhost
GRADIO_PORT=7865
API_BASE_URL=http://localhost:8000
SIMULATION_MODE=true
PLAYWRIGHT_TIMEOUT=30000
```

### Test Data

Ensure test database has:
- [ ] At least 3 tokens for discovery
- [ ] At least 5 wallets (2+ watchlisted)
- [ ] At least 1 cluster with 3+ members
- [ ] Mix of signal outcomes (TRADE/NO TRADE)
- [ ] Active and closed positions
- [ ] Orders in various states (pending, filled, failed)

---

## Running Tests

### Full Suite

```bash
pytest tests/e2e/ -v --tb=short
```

### Single Spec

```bash
# Run dashboard navigation tests
pytest tests/e2e/gradio/test_01_dashboard.py -v

# Run signal scoring tests
pytest tests/e2e/gradio/test_05_signals.py -v
```

### Headed Mode (Debug)

```bash
pytest tests/e2e/ --headed --slowmo=500
```

### Generate Report

```bash
pytest tests/e2e/ --html=reports/e2e-report.html --self-contained-html
```

---

## Gradio Locator Strategy

All specs use the `elem_id` convention for reliable element selection:

```python
# Gradio component with elem_id
gr.Dataframe(elem_id="signals-table")

# Playwright selector
signals_table = page.locator("#signals-table")
```

### Locator Categories

| Category | Pattern | Example |
|----------|---------|---------|
| Tables | `#*-table` | `#signals-table`, `#positions-table` |
| Buttons | `#*-btn` | `#refresh-btn`, `#apply-btn` |
| Filters | `#*-filter-*` | `#positions-filter-active` |
| Inputs | `#*-input` | `#token-input` |
| Status | `#*-status` | `#webhook-status` |
| Sliders | `#config-*` | `#config-trade-threshold` |

---

## Epic 14 Changes Summary

### Removed Features (No Tests Needed)
- Exit Simulation page (`exit_simulator.py`)
- What-If calculator (`what_if_calculator.py`)
- Backtest module
- Complex 4-factor scoring

### Simplified Features (Updated Tests)
- **Scoring**: 8 params instead of 30+
- **Threshold**: Single 0.65 instead of dual
- **WalletCache**: Gets cluster data from ClusterService
- **Cluster Integration**: Automatic network onboarding

### New Scoring Formula

```
Final Score = Wallet Score × Cluster Boost

Where:
- Wallet Score = (win_rate × 0.6 + pnl_norm × 0.4) × leader_bonus
- Cluster Boost = 1.0x to 1.8x
- Threshold = 0.65
```

---

## Test Data Fixtures

See [Master Document](../e2e-test-scenarios-v1.md#20-test-data--fixtures) for complete fixture definitions.

### Quick Reference

```python
# conftest.py fixtures
@pytest.fixture
def watchlisted_wallet() -> str:
    return "TestWatchlistedWallet123"

@pytest.fixture
def valid_token_mint() -> str:
    return "ValidSafeTokenMint456"

@pytest.fixture
def webhook_payload(watchlisted_wallet: str, valid_token_mint: str) -> dict:
    return {
        "type": "TRANSACTION",
        "transactions": [{
            "signature": f"test_{uuid4().hex[:8]}",
            "type": "SWAP",
            "feePayer": watchlisted_wallet,
            "tokenTransfers": [{
                "mint": valid_token_mint,
                "toUserAccount": watchlisted_wallet,
                "tokenAmount": 1000000,
            }]
        }]
    }
```

---

## Maintenance

### Adding New Tests

1. Create test case in appropriate spec file
2. Add locator to spec's locator section
3. Ensure `elem_id` exists in Gradio component
4. Update this README if adding new spec

### Updating for New Features

1. Check Epic requirements
2. Update affected spec files
3. Update priority matrix if needed
4. Run full suite to verify

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Element not found | Verify `elem_id` in Gradio component |
| Timeout | Increase `PLAYWRIGHT_TIMEOUT` or add explicit waits |
| Stale element | Add `page.wait_for_timeout(500)` after actions |
| Gradio not loading | Check if `gr.Blocks()` uses `server_name="0.0.0.0"` |

### Debug Tips

```python
# Take screenshot on failure
page.screenshot(path="debug.png")

# Print page content
print(page.content())

# Pause for inspection
page.pause()
```

---

## Related Documentation

- [Master E2E Scenarios](../e2e-test-scenarios-v1.md)
- [Epic 14 Simplification](../../sprint-artifacts/(In%20progress)%20epic-14-simplification/epics.md)
- [Playwright Best Practices](https://playwright.dev/python/docs/best-practices)
