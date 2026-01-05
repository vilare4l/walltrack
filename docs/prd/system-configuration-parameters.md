# System Configuration Parameters

All system behavior should be configurable to allow operator adaptation to market conditions and risk tolerance. This section defines all configurable parameters with their default values.

### Trading Parameters

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Starting Capital** | 300€ | 50€ - unlimited | Total capital allocated to trading | Config UI |
| **Risk Per Trade** | 2% | 0.5% - 5% | Percentage of capital per position | Config UI |
| **Position Sizing Mode** | Fixed % | Fixed % / Dynamic | How position sizes are calculated | Config UI |

### Risk Management Parameters

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Stop Loss** | -20% | -5% to -50% | Maximum loss per position before exit | Per-wallet default + per-position override |
| **Trailing Stop %** | 15% | 5% - 30% | Distance below peak price for trailing stop | Per-wallet default + per-position override |
| **Slippage Tolerance** | 3% | 1% - 10% | Maximum acceptable slippage on Jupiter swaps | Config UI |
| **Max Drawdown (Circuit Breaker)** | 20% | 10% - 50% | Total portfolio loss triggering trading halt | Config UI |
| **Min Win Rate Alert** | 40% | 30% - 60% | Win rate threshold triggering wallet review | Config UI |
| **Consecutive Max-Loss Trigger** | 3 trades | 2 - 10 | Consecutive stop-loss hits triggering review | Config UI |

### Safety Analysis Parameters

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Safety Score Threshold** | 0.60 | 0.40 - 0.90 | Minimum score for trade execution | Config UI |
| **Liquidity Check Weight** | 25% | 0% - 50% | Weight in safety score calculation | Config file (advanced) |
| **Holder Distribution Weight** | 25% | 0% - 50% | Weight in safety score calculation | Config file (advanced) |
| **Contract Analysis Weight** | 25% | 0% - 50% | Weight in safety score calculation | Config file (advanced) |
| **Age Check Weight** | 25% | 0% - 50% | Weight in safety score calculation | Config file (advanced) |
| **Min Liquidity** | $50K | $10K - $500K | Minimum token liquidity threshold | Config UI |
| **Max Top 10 Holder %** | 80% | 50% - 95% | Maximum concentration in top 10 holders | Config UI |
| **Min Token Age** | 24 hours | 1h - 7 days | Minimum token age before trading | Config UI |

### Exit Strategy Parameters (Per-Wallet Defaults)

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Scaling Level 1** | 50% @ 2x | 10-100% @ 1.2x-10x | First scaling out level | Per-wallet config |
| **Scaling Level 2** | 25% @ 3x | 10-100% @ 1.5x-20x | Second scaling out level | Per-wallet config |
| **Scaling Level 3** | 25% hold | 0-100% @ any multiplier | Final scaling level or hold | Per-wallet config |
| **Mirror Exit Enabled** | true | true/false | Follow source wallet exits | Per-wallet config |
| **Trailing Stop Enabled** | false | true/false | Activate trailing stop | Per-wallet config |
| **Trailing Activation Threshold** | +20% | +10% to +100% | Profit level to activate trailing stop | Per-wallet config |

**Note:** All exit strategy parameters have per-wallet defaults but can be overridden per-position in the Dashboard UI.

### System Monitoring Parameters

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Price Polling Interval** | 45s | 15s - 120s | DexScreener API polling frequency | Config UI |
| **Webhook Timeout Alert** | 48 hours | 12h - 7 days | No signals threshold for system health alert | Config UI |
| **Max Price Data Staleness** | 5 minutes | 1m - 30m | Alert if price data not updated | Config file (advanced) |
| **Auto-Restart on Crash** | true | true/false | System auto-restart behavior | Config file (advanced) |

### Performance Thresholds (Circuit Breakers)

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Min Win Rate (50+ trades)** | 40% | 30% - 60% | Halt trading if below this rate | Config UI |
| **Max Drawdown** | 20% | 10% - 50% | Halt trading if exceeded | Config UI |
| **Consecutive Max-Loss** | 3 trades | 2 - 10 | Flag for review after N stop-losses | Config UI |

### Configuration Persistence

**Storage:** All configuration parameters persist in Supabase `config` table.

**Change Propagation:**
- Config UI changes: Apply immediately to new signals/positions
- Per-wallet changes: Apply immediately to that wallet's new positions
- Per-position overrides: Apply only to that specific position

**Config Backup:**
- Configuration exported to JSON on every change
- Stored in `config_backup/` directory with timestamp
- Allows rollback to previous config if needed

**Validation:**
- All parameter changes validated before persistence
- Range checks enforced (e.g., stop-loss must be between -5% and -50%)
- Invalid values rejected with clear error message

---
