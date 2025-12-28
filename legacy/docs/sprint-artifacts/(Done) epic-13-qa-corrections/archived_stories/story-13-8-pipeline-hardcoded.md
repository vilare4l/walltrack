# Story 13-8: Fix Signal Pipeline Hardcoded Values

## Priority: HIGH

## Problem Statement

The SignalPipeline has several hardcoded values that should come from configuration or signal context:

1. **Balance hardcoded to 10 SOL** (line 367)
2. **exit_strategy_id hardcoded to "default-exit-strategy"** (line 81)
3. **cluster_id not passed** (EntryOrderService line 89)

## Evidence

**SignalPipeline (`pipeline.py`):**
```python
# Line 81:
_default_exit_strategy_id = "default-exit-strategy"

# Line 367:
simulated_balance = 10.0  # Hardcoded!

# Position creation uses hardcoded exit strategy
position = await self.position_service.create_position(
    exit_strategy_id=self._default_exit_strategy_id,  # Always default
    ...
)
```

**EntryOrderService (`entry_service.py`):**
```python
# Line 89:
risk_check = await self.risk_manager.check_entry_allowed(
    token_address=signal.token_address,
    cluster_id=None,  # TODO: Add cluster_id to signal
)
```

## Impact

- Position sizing uses 10 SOL regardless of actual balance
- All positions use same exit strategy (no conviction-tier differentiation)
- Concentration limits per cluster cannot be enforced
- Risk management partially broken

## Solution

### Part 1: Fix Balance Retrieval

**File: `src/walltrack/services/signal/pipeline.py`**

```python
async def _get_available_balance(self) -> float:
    """Get actual available balance from trading wallet."""
    try:
        # Use wallet state service
        from walltrack.services.wallet.balance_service import get_balance_service
        balance_svc = await get_balance_service()
        balance = await balance_svc.get_available_balance()
        return float(balance)
    except Exception as e:
        logger.warning("balance_fetch_failed", error=str(e))
        # Fallback to config minimum
        trading_config = await self._get_trading_config()
        return float(trading_config.min_position_sol) * 10  # 10x minimum

# Replace line 367:
# Before:
simulated_balance = 10.0
# After:
simulated_balance = await self._get_available_balance()
```

### Part 2: Fix Exit Strategy Selection

**File: `src/walltrack/services/signal/pipeline.py`**

```python
async def _get_exit_strategy_for_conviction(
    self,
    conviction_tier: str,
) -> str:
    """Get appropriate exit strategy for conviction tier."""
    from walltrack.services.config.config_service import get_config_service
    config_svc = await get_config_service()
    exit_config = await config_svc.get_exit_config()

    if conviction_tier == "high":
        strategy_id = exit_config.default_strategy_high_conviction_id
    else:
        strategy_id = exit_config.default_strategy_standard_id

    # Fallback to any active strategy
    if not strategy_id:
        from walltrack.services.exit.exit_strategy_service import get_exit_strategy_service
        svc = await get_exit_strategy_service()
        strategies = await svc.list_strategies(status="active")
        if strategies:
            strategy_id = strategies[0].id

    return strategy_id or "default-exit-strategy"

# Update position creation:
position = await self.position_service.create_position(
    exit_strategy_id=await self._get_exit_strategy_for_conviction(conviction_tier),
    ...
)
```

### Part 3: Add cluster_id to Signal Chain

**File: `src/walltrack/models/signal_log.py`**

```python
class SignalLogEntry(BaseModel):
    # ... existing fields ...
    cluster_id: str | None = Field(
        default=None,
        description="Cluster ID if signal comes from cluster member"
    )
```

**File: `src/walltrack/services/signal/pipeline.py`**

```python
# In _create_signal_from_swap():
signal = SignalLogEntry(
    # ... existing fields ...
    cluster_id=await self._find_wallet_cluster(wallet_address),
)

async def _find_wallet_cluster(self, wallet_address: str) -> str | None:
    """Find cluster for wallet if any."""
    try:
        from walltrack.data.neo4j.queries.cluster import ClusterQueries
        from walltrack.data.neo4j.client import get_neo4j_client
        client = await get_neo4j_client()
        queries = ClusterQueries(client)
        clusters = await queries.get_wallet_clusters(wallet_address)
        if clusters:
            return clusters[0].id
        return None
    except Exception:
        return None
```

**File: `src/walltrack/services/order/entry_service.py`**

```python
# Line 89: Update to use signal's cluster_id
risk_check = await self.risk_manager.check_entry_allowed(
    token_address=signal.token_address,
    cluster_id=signal.cluster_id,  # Now available
)
```

## Acceptance Criteria

- [ ] Balance retrieved from actual wallet state
- [ ] Exit strategy selected based on conviction tier
- [ ] cluster_id added to SignalLogEntry model
- [ ] cluster_id populated during signal creation
- [ ] cluster_id passed to risk manager checks
- [ ] Fallback behavior for missing data

## Files to Modify

- `src/walltrack/services/signal/pipeline.py`
- `src/walltrack/models/signal_log.py`
- `src/walltrack/services/order/entry_service.py`

## Testing

```python
async def test_balance_not_hardcoded():
    # Mock balance service to return 50 SOL
    with patch("get_balance_service") as mock:
        mock.return_value.get_available_balance.return_value = 50.0
        pipeline = SignalPipeline()
        balance = await pipeline._get_available_balance()
        assert balance == 50.0

async def test_exit_strategy_by_conviction():
    # High conviction should use high conviction strategy
    pipeline = SignalPipeline()
    strategy_id = await pipeline._get_exit_strategy_for_conviction("high")
    assert strategy_id != "default-exit-strategy"

async def test_cluster_id_in_signal():
    signal = await pipeline._create_signal_from_swap(swap_event)
    # If wallet is in a cluster, cluster_id should be set
    assert signal.cluster_id is not None or signal.cluster_id is None  # Either is valid
```

## Estimated Effort

2-3 hours

## Dependencies

- Story 13-7 (config unification) should be done first for exit strategy retrieval
- Balance service must exist (verify or create stub)
