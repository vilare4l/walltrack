# Story 13-7: Unify Config Systems

## Priority: HIGH

## Problem Statement

Two separate config systems exist with incompatible structures:

1. **Old System** (`public.position_sizing_config`):
   - Used by `PositionConfigRepository`
   - Used by `PositionSizer`
   - Fields: base_position_pct, min_position_sol, max_position_sol, conviction multipliers

2. **New System** (`walltrack.risk_config`):
   - Used by `ConfigService`
   - Used by API config endpoints
   - Fields: risk_per_trade_pct, sizing_mode, daily_loss_limit_pct, concentration limits

## Evidence

**PositionSizer (`position_sizer.py` line 89):**
```python
self._config_repo = PositionConfigRepository(client)
# Uses public.position_sizing_config
```

**ConfigService (`config_service.py` line 155):**
```python
result = await client.table(f"{table}_config")  # risk_config
# Uses walltrack.risk_config
```

## Impact

- Config changes in UI don't affect PositionSizer
- PositionSizer uses old config table values
- Risk config in UI is disconnected from actual sizing logic
- User confusion about which config to edit

## Solution

Migrate PositionSizer to use ConfigService.

### Changes Required

**File: `src/walltrack/services/trade/position_sizer.py`**

```python
# Before:
from walltrack.data.supabase.repositories.position_config_repo import PositionConfigRepository

class PositionSizer:
    def __init__(self, client):
        self._config_repo = PositionConfigRepository(client)

    async def _load_config(self) -> PositionSizingConfig:
        return await self._config_repo.get_config()

# After:
from walltrack.services.config.config_service import get_config_service

class PositionSizer:
    def __init__(self):
        self._config_service = None

    async def _get_config_service(self):
        if self._config_service is None:
            self._config_service = await get_config_service()
        return self._config_service

    async def _load_config(self) -> PositionSizingConfig:
        config_svc = await self._get_config_service()

        # Get both trading and risk configs
        trading = await config_svc.get_trading_config()
        risk = await config_svc.get_risk_config()

        # Map to PositionSizingConfig model
        return PositionSizingConfig(
            # From trading_config:
            base_position_pct=float(trading.base_position_size_pct),
            min_position_sol=float(trading.min_position_sol),
            max_position_sol=float(trading.max_position_sol),
            max_concurrent_positions=trading.max_concurrent_positions,
            high_conviction_threshold=float(trading.high_conviction_threshold),
            high_conviction_multiplier=float(trading.high_conviction_multiplier),

            # From risk_config:
            sizing_mode=SizingMode(risk.sizing_mode),
            risk_per_trade_pct=float(risk.risk_per_trade_pct),
            daily_loss_limit_pct=float(risk.daily_loss_limit_pct),
            daily_loss_limit_enabled=risk.daily_loss_limit_enabled,
            max_token_concentration_pct=float(risk.max_concentration_token_pct),
            max_cluster_concentration_pct=float(risk.max_concentration_cluster_pct),
            max_positions_per_cluster=risk.max_positions_per_cluster,
            drawdown_reduction_enabled=True,
            drawdown_reduction_tiers=[
                DrawdownReductionTier(**tier)
                for tier in risk.drawdown_reduction_tiers
            ],
        )
```

**Also update `get_position_sizer()`:**
```python
async def get_position_sizer() -> PositionSizer:
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = PositionSizer()  # No client needed
    return _position_sizer
```

## Field Mapping

| Old Field (position_sizing_config) | New Field (trading/risk_config) |
|-----------------------------------|--------------------------------|
| base_position_pct | trading.base_position_size_pct |
| min_position_sol | trading.min_position_sol |
| max_position_sol | trading.max_position_sol |
| max_concurrent_positions | trading.max_concurrent_positions |
| high_conviction_threshold | trading.high_conviction_threshold |
| high_conviction_multiplier | trading.high_conviction_multiplier |
| risk_per_trade_pct | risk.risk_per_trade_pct |
| sizing_mode | risk.sizing_mode |
| daily_loss_limit_pct | risk.daily_loss_limit_pct |
| max_token_concentration_pct | risk.max_concentration_token_pct |
| max_cluster_concentration_pct | risk.max_concentration_cluster_pct |
| max_positions_per_cluster | risk.max_positions_per_cluster |
| drawdown_reduction_tiers | risk.drawdown_reduction_tiers |

## Acceptance Criteria

- [ ] PositionSizer uses ConfigService instead of PositionConfigRepository
- [ ] All config fields correctly mapped
- [ ] Config changes in UI affect position sizing immediately (hot-reload)
- [ ] PositionConfigRepository marked as deprecated
- [ ] Tests updated to use new config source

## Files to Modify

- `src/walltrack/services/trade/position_sizer.py`
- `src/walltrack/data/supabase/repositories/position_config_repo.py` (deprecate)

## Testing

```python
async def test_config_hot_reload():
    sizer = await get_position_sizer()
    config_svc = await get_config_service()

    # Get current max
    config1 = await sizer._load_config()
    original_max = config1.max_position_sol

    # Update via config service
    await config_svc.update_trading_config(max_position_sol=5.0)

    # Clear cache and reload
    await config_svc.refresh("trading")

    config2 = await sizer._load_config()
    assert config2.max_position_sol == 5.0
```

## Estimated Effort

2-3 hours

## Migration Notes

- Old `position_sizing_config` table can be archived after verification
- No data migration needed (new tables already have defaults)
- Users should be notified to use new config UI
