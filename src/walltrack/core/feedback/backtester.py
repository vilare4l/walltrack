"""Backtest preview service for parameter optimization."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import structlog

from walltrack.core.feedback.backtest_models import (
    ApplySettingsRequest,
    ApplySettingsResult,
    BacktestConfig,
    BacktestProgress,
    BacktestResult,
    BacktestStatus,
    HistoricalSignal,
    MetricsComparison,
    PerformanceMetrics,
    ScoringWeights,
    SimulatedTrade,
    TradeComparison,
)
from walltrack.data.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


class BacktestService:
    """Service for running backtest previews."""

    def __init__(self):
        self._supabase = None
        self._running_backtests: dict[str, BacktestProgress] = {}
        self._signal_cache: dict[str, list[HistoricalSignal]] = {}
        self._cache_ttl_minutes = 30

    async def _get_supabase(self):
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def run_backtest(
        self,
        config: BacktestConfig,
        progress_callback: Callable[[BacktestProgress], None] | None = None,
    ) -> BacktestResult:
        """Run a backtest with the given configuration.

        Target completion time: < 30 seconds for 6 months of data.
        """
        backtest_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        logger.info(
            "backtest_started",
            backtest_id=backtest_id,
            start_date=str(config.start_date),
            end_date=str(config.end_date),
        )

        # Initialize progress
        progress = BacktestProgress(
            backtest_id=backtest_id,
            status=BacktestStatus.RUNNING,
            signals_processed=0,
            total_signals=0,
            current_phase="Loading signals",
            elapsed_seconds=0,
        )
        self._running_backtests[backtest_id] = progress

        try:
            # Phase 1: Load historical signals
            signals = await self._load_historical_signals(config)
            progress.total_signals = len(signals)
            progress.current_phase = "Rescoring signals"

            if progress_callback:
                await progress_callback(progress)

            # Phase 2: Rescore signals with new weights
            rescored_signals = []
            for i, signal in enumerate(signals):
                rescored = await self._rescore_signal(signal, config.scoring_weights)
                rescored_signals.append(rescored)

                progress.signals_processed = i + 1
                progress.elapsed_seconds = int(
                    (datetime.now(UTC) - started_at).total_seconds()
                )

                # Estimate remaining time
                if i > 0:
                    avg_time_per_signal = progress.elapsed_seconds / (i + 1)
                    remaining_signals = len(signals) - i - 1
                    progress.estimated_remaining_seconds = int(
                        avg_time_per_signal * remaining_signals
                    )

                # Callback every 10 signals to reduce overhead
                if progress_callback and i % 10 == 0:
                    await progress_callback(progress)

            # Phase 3: Simulate trades
            progress.current_phase = "Simulating trades"
            if progress_callback:
                await progress_callback(progress)

            simulated_trades = await self._simulate_trades(rescored_signals, config)

            # Phase 4: Calculate metrics
            progress.current_phase = "Calculating metrics"
            if progress_callback:
                await progress_callback(progress)

            actual_metrics = await self._calculate_actual_metrics(config)
            simulated_metrics = self._calculate_simulated_metrics(simulated_trades)

            metrics_comparison = MetricsComparison(
                actual=actual_metrics, simulated=simulated_metrics
            )

            # Phase 5: Build trade comparisons
            trade_comparisons = await self._build_trade_comparisons(
                signals, simulated_trades
            )

            # Complete
            completed_at = datetime.now(UTC)
            duration_seconds = int((completed_at - started_at).total_seconds())

            result = BacktestResult(
                id=backtest_id,
                config=config,
                status=BacktestStatus.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                total_signals_analyzed=len(signals),
                signals_above_threshold=sum(
                    1
                    for s in rescored_signals
                    if s.original_score >= config.score_threshold
                ),
                metrics_comparison=metrics_comparison,
                simulated_trades=simulated_trades,
                trade_comparisons=trade_comparisons,
            )

            # Store result
            await self._store_backtest_result(result)

            logger.info(
                "backtest_completed",
                backtest_id=backtest_id,
                duration_seconds=duration_seconds,
                signals_analyzed=len(signals),
                simulated_trades=len(simulated_trades),
            )

            return result

        except Exception as e:
            logger.error("backtest_failed", backtest_id=backtest_id, error=str(e))

            return BacktestResult(
                id=backtest_id,
                config=config,
                status=BacktestStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error_message=str(e),
            )

        finally:
            if backtest_id in self._running_backtests:
                del self._running_backtests[backtest_id]

    async def _load_historical_signals(
        self, config: BacktestConfig
    ) -> list[HistoricalSignal]:
        """Load historical signals for the date range."""
        # Check cache first
        cache_key = f"{config.start_date}_{config.end_date}"
        if cache_key in self._signal_cache:
            logger.debug("using_cached_signals", cache_key=cache_key)
            return self._signal_cache[cache_key]

        supabase = await self._get_supabase()

        # Load signals
        response = (
            await supabase.table("signals")
            .select("id, timestamp, token_address, source_wallet, score, score_factors")
            .gte("timestamp", config.start_date.isoformat())
            .lte("timestamp", f"{config.end_date}T23:59:59")
            .execute()
        )

        signal_data = response.data or []

        # Load corresponding trades
        trades_response = (
            await supabase.table("trade_outcomes")
            .select("signal_id, entry_price, exit_price, realized_pnl_sol")
            .gte("entry_timestamp", config.start_date.isoformat())
            .lte("entry_timestamp", f"{config.end_date}T23:59:59")
            .execute()
        )

        trades_by_signal = {t["signal_id"]: t for t in (trades_response.data or [])}

        # Load price history for each token (batch)
        token_addresses = list({s["token_address"] for s in signal_data})
        price_histories = await self._load_price_histories(
            token_addresses, config.start_date, config.end_date
        )

        # Build HistoricalSignal objects
        signals = []
        for s in signal_data:
            trade = trades_by_signal.get(s["id"])
            price_history = price_histories.get(s["token_address"], [])

            # Find price at signal time and max/min after
            signal_time = datetime.fromisoformat(
                s["timestamp"].replace("Z", "+00:00")
            )
            prices_after = [(t, p) for t, p in price_history if t >= signal_time]

            price_at_signal = Decimal("0")
            max_price_after = None
            min_price_after = None

            if prices_after:
                price_at_signal = prices_after[0][1]
                max_price_after = max(p for _, p in prices_after)
                min_price_after = min(p for _, p in prices_after)

            signal = HistoricalSignal(
                id=s["id"],
                timestamp=signal_time,
                token_address=s["token_address"],
                source_wallet=s["source_wallet"],
                original_score=Decimal(str(s.get("score", 0))),
                original_factors=s.get("score_factors", {}),
                was_traded=trade is not None,
                actual_entry_price=(
                    Decimal(str(trade["entry_price"])) if trade else None
                ),
                actual_exit_price=(
                    Decimal(str(trade["exit_price"])) if trade else None
                ),
                actual_pnl_sol=(
                    Decimal(str(trade["realized_pnl_sol"])) if trade else None
                ),
                price_at_signal=price_at_signal,
                price_history=prices_after[:100],  # Limit for memory
                max_price_after=max_price_after,
                min_price_after=min_price_after,
            )
            signals.append(signal)

        # Cache results
        self._signal_cache[cache_key] = signals

        return signals

    async def _load_price_histories(
        self, token_addresses: list[str], start_date, end_date
    ) -> dict[str, list[tuple[datetime, Decimal]]]:
        """Load price histories for tokens."""
        if not token_addresses:
            return {}

        supabase = await self._get_supabase()

        # Batch load price data
        response = (
            await supabase.table("token_prices")
            .select("token_address, timestamp, price")
            .in_("token_address", token_addresses)
            .gte("timestamp", start_date.isoformat())
            .lte("timestamp", f"{end_date}T23:59:59")
            .order("timestamp")
            .execute()
        )

        # Group by token
        histories: dict[str, list[tuple[datetime, Decimal]]] = {}
        for row in response.data or []:
            addr = row["token_address"]
            if addr not in histories:
                histories[addr] = []
            histories[addr].append(
                (
                    datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                    Decimal(str(row["price"])),
                )
            )

        return histories

    async def _rescore_signal(
        self, signal: HistoricalSignal, weights: ScoringWeights
    ) -> HistoricalSignal:
        """Rescore a signal with new weights."""
        factors = signal.original_factors

        # Calculate new score with new weights
        new_score = (
            Decimal(str(factors.get("wallet_score", 0))) * weights.wallet_score_weight
            + Decimal(str(factors.get("token_metrics", 0)))
            * weights.token_metrics_weight
            + Decimal(str(factors.get("liquidity", 0))) * weights.liquidity_weight
            + Decimal(str(factors.get("holder_distribution", 0)))
            * weights.holder_distribution_weight
            + Decimal(str(factors.get("momentum", 0))) * weights.momentum_weight
        ) * 100  # Scale to 0-100

        # Create copy with new score
        return HistoricalSignal(
            id=signal.id,
            timestamp=signal.timestamp,
            token_address=signal.token_address,
            source_wallet=signal.source_wallet,
            original_score=new_score.quantize(Decimal("0.01")),
            original_factors=signal.original_factors,
            was_traded=signal.was_traded,
            actual_entry_price=signal.actual_entry_price,
            actual_exit_price=signal.actual_exit_price,
            actual_pnl_sol=signal.actual_pnl_sol,
            price_at_signal=signal.price_at_signal,
            price_history=signal.price_history,
            max_price_after=signal.max_price_after,
            min_price_after=signal.min_price_after,
        )

    async def _simulate_trades(
        self, signals: list[HistoricalSignal], config: BacktestConfig
    ) -> list[SimulatedTrade]:
        """Simulate trades based on rescored signals."""
        simulated_trades = []

        for signal in signals:
            # Would we trade this signal?
            would_trade = signal.original_score >= config.score_threshold

            if not would_trade:
                continue

            if signal.price_at_signal == 0:
                continue

            # Calculate position size
            position_size = config.position_sizing.base_position_sol
            if config.position_sizing.scale_with_confidence:
                confidence_factor = signal.original_score / Decimal("100")
                position_size = min(
                    position_size
                    * confidence_factor
                    * config.position_sizing.confidence_multiplier,
                    config.position_sizing.max_position_sol,
                )

            # Simulate exit
            entry_price = signal.price_at_signal
            exit_price, exit_reason = self._simulate_exit(signal, config)

            # Calculate PnL
            if entry_price > 0:
                price_change_percent = ((exit_price - entry_price) / entry_price) * 100
                gross_pnl = position_size * (price_change_percent / 100)
            else:
                gross_pnl = Decimal("0")

            # Apply costs
            slippage_cost = position_size * (config.slippage_percent / 100)
            gas_cost = (
                config.gas_cost_sol if config.include_gas_costs else Decimal("0")
            )

            trade = SimulatedTrade(
                signal_id=signal.id,
                token_address=signal.token_address,
                source_wallet=signal.source_wallet,
                simulated_score=signal.original_score,
                would_trade=True,
                entry_price=entry_price,
                exit_price=exit_price,
                exit_reason=exit_reason,
                position_size_sol=position_size.quantize(Decimal("0.0001")),
                gross_pnl_sol=gross_pnl.quantize(Decimal("0.0001")),
                slippage_cost_sol=slippage_cost.quantize(Decimal("0.0001")),
                gas_cost_sol=gas_cost,
            )
            simulated_trades.append(trade)

        return simulated_trades

    def _simulate_exit(
        self, signal: HistoricalSignal, config: BacktestConfig
    ) -> tuple[Decimal, str]:
        """Simulate exit based on price history and exit strategy."""
        entry_price = signal.price_at_signal
        exit_config = config.exit_strategy

        if not signal.price_history or entry_price == 0:
            return entry_price, "no_data"

        # Calculate target prices
        stop_loss_price = entry_price * (1 - exit_config.stop_loss_percent / 100)
        take_profit_price = entry_price * (1 + exit_config.take_profit_percent / 100)

        # Track trailing stop
        peak_price = entry_price
        trailing_stop_percent = exit_config.trailing_stop_percent

        # Simulate through price history
        exit_result: tuple[Decimal, str] | None = None
        for timestamp, price in signal.price_history:
            # Check time limit
            hold_duration = (timestamp - signal.timestamp).total_seconds() / 60
            if hold_duration >= exit_config.max_hold_minutes:
                exit_result = (price, "time_limit")
                break

            # Update trailing stop
            peak_price = max(peak_price, price)
            trailing_stop_price = peak_price * (1 - trailing_stop_percent / 100)

            # Check exits in priority order
            if price <= stop_loss_price:
                exit_result = (stop_loss_price, "stop_loss")
                break
            if price >= take_profit_price:
                exit_result = (take_profit_price, "take_profit")
                break
            if price <= trailing_stop_price and peak_price > entry_price:
                exit_result = (trailing_stop_price, "trailing_stop")
                break

        # Return exit result or end of data
        if exit_result:
            return exit_result
        return signal.price_history[-1][1], "end_of_data"

    async def _calculate_actual_metrics(
        self, config: BacktestConfig
    ) -> PerformanceMetrics:
        """Calculate actual metrics for the date range."""
        supabase = await self._get_supabase()

        response = (
            await supabase.table("trade_outcomes")
            .select("*")
            .gte("exit_timestamp", config.start_date.isoformat())
            .lte("exit_timestamp", f"{config.end_date}T23:59:59")
            .execute()
        )

        trades = response.data or []

        if not trades:
            return PerformanceMetrics()

        winning = [
            t for t in trades if Decimal(str(t.get("realized_pnl_sol", 0))) > 0
        ]
        losing = [
            t for t in trades if Decimal(str(t.get("realized_pnl_sol", 0))) <= 0
        ]

        total_pnl = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in trades)
        gross_profit = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in winning)
        gross_loss = sum(
            abs(Decimal(str(t.get("realized_pnl_sol", 0)))) for t in losing
        )

        avg_win = gross_profit / len(winning) if winning else Decimal("0")
        avg_loss = gross_loss / len(losing) if losing else Decimal("0")

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(trades)

        # Calculate max consecutive losses
        max_consecutive = self._calculate_max_consecutive_losses(trades)

        return PerformanceMetrics(
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl_sol=total_pnl.quantize(Decimal("0.0001")),
            gross_profit_sol=gross_profit.quantize(Decimal("0.0001")),
            gross_loss_sol=gross_loss.quantize(Decimal("0.0001")),
            average_win_sol=avg_win.quantize(Decimal("0.0001")),
            average_loss_sol=avg_loss.quantize(Decimal("0.0001")),
            max_drawdown_sol=max_drawdown.quantize(Decimal("0.0001")),
            max_consecutive_losses=max_consecutive,
        )

    def _calculate_simulated_metrics(
        self, trades: list[SimulatedTrade]
    ) -> PerformanceMetrics:
        """Calculate metrics from simulated trades."""
        if not trades:
            return PerformanceMetrics()

        winning = [t for t in trades if t.is_win]
        losing = [t for t in trades if not t.is_win]

        total_pnl = sum(t.net_pnl_sol for t in trades)
        gross_profit = sum(t.net_pnl_sol for t in winning)
        gross_loss = sum(abs(t.net_pnl_sol) for t in losing)

        avg_win = gross_profit / len(winning) if winning else Decimal("0")
        avg_loss = gross_loss / len(losing) if losing else Decimal("0")

        # Calculate max drawdown from simulated trades
        max_drawdown = Decimal("0")
        peak = Decimal("0")
        cumulative = Decimal("0")

        for trade in trades:
            cumulative += trade.net_pnl_sol
            peak = max(peak, cumulative)
            drawdown = peak - cumulative
            max_drawdown = max(max_drawdown, drawdown)

        # Max consecutive losses
        max_consecutive = 0
        current_consecutive = 0
        for trade in trades:
            if not trade.is_win:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return PerformanceMetrics(
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl_sol=total_pnl.quantize(Decimal("0.0001")),
            gross_profit_sol=gross_profit.quantize(Decimal("0.0001")),
            gross_loss_sol=gross_loss.quantize(Decimal("0.0001")),
            average_win_sol=avg_win.quantize(Decimal("0.0001")),
            average_loss_sol=avg_loss.quantize(Decimal("0.0001")),
            max_drawdown_sol=max_drawdown.quantize(Decimal("0.0001")),
            max_consecutive_losses=max_consecutive,
        )

    def _calculate_max_drawdown(self, trades: list[dict]) -> Decimal:
        """Calculate maximum drawdown from trade list."""
        max_drawdown = Decimal("0")
        peak = Decimal("0")
        cumulative = Decimal("0")

        for trade in sorted(trades, key=lambda t: t.get("exit_timestamp", "")):
            pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))
            cumulative += pnl
            peak = max(peak, cumulative)
            drawdown = peak - cumulative
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    def _calculate_max_consecutive_losses(self, trades: list[dict]) -> int:
        """Calculate maximum consecutive losses."""
        max_consecutive = 0
        current_consecutive = 0

        for trade in sorted(trades, key=lambda t: t.get("exit_timestamp", "")):
            pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))
            if pnl <= 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    async def _build_trade_comparisons(
        self, signals: list[HistoricalSignal], simulated_trades: list[SimulatedTrade]
    ) -> list[TradeComparison]:
        """Build trade-by-trade comparisons."""
        simulated_by_signal = {t.signal_id: t for t in simulated_trades}

        comparisons = []
        for signal in signals:
            simulated = simulated_by_signal.get(signal.id)

            comparison = TradeComparison(
                signal_id=signal.id,
                token_address=signal.token_address,
                timestamp=signal.timestamp,
                actual_traded=signal.was_traded,
                actual_pnl_sol=signal.actual_pnl_sol,
                simulated_traded=simulated is not None,
                simulated_pnl_sol=simulated.net_pnl_sol if simulated else None,
            )
            comparisons.append(comparison)

        # Sort by change impact (changed outcomes first)
        comparisons.sort(key=lambda c: (not c.outcome_changed, not c.pnl_changed))

        return comparisons

    async def _store_backtest_result(self, result: BacktestResult):
        """Store backtest result in database."""
        supabase = await self._get_supabase()

        await supabase.table("backtest_results").insert(
            {
                "id": result.id,
                "config": result.config.model_dump(mode="json"),
                "status": result.status.value,
                "started_at": result.started_at.isoformat(),
                "completed_at": (
                    result.completed_at.isoformat() if result.completed_at else None
                ),
                "duration_seconds": result.duration_seconds,
                "total_signals_analyzed": result.total_signals_analyzed,
                "metrics_comparison": (
                    result.metrics_comparison.model_dump(mode="json")
                    if result.metrics_comparison
                    else None
                ),
                "trade_comparisons_count": len(result.trade_comparisons),
                "error_message": result.error_message,
            }
        ).execute()

    async def apply_settings(
        self, request: ApplySettingsRequest
    ) -> ApplySettingsResult:
        """Apply backtest settings to production configuration."""
        if not request.confirm_apply:
            return ApplySettingsResult(
                success=False,
                backtest_id=request.backtest_id,
                applied_at=datetime.now(UTC),
                error_message="confirm_apply must be True to apply settings",
            )

        supabase = await self._get_supabase()

        # Load backtest result
        response = (
            await supabase.table("backtest_results")
            .select("*")
            .eq("id", request.backtest_id)
            .single()
            .execute()
        )

        if not response.data:
            return ApplySettingsResult(
                success=False,
                backtest_id=request.backtest_id,
                applied_at=datetime.now(UTC),
                error_message="Backtest not found",
            )

        config_data = response.data["config"]
        config = BacktestConfig(**config_data)

        changes_applied = []
        previous_values = {}

        try:
            # Apply scoring weights
            if request.apply_scoring_weights:
                prev = await self._get_current_weights()
                await self._apply_scoring_weights(config.scoring_weights)
                changes_applied.append("scoring_weights")
                previous_values["scoring_weights"] = prev

            # Apply threshold
            if request.apply_threshold:
                prev = await self._get_current_threshold()
                await self._apply_threshold(config.score_threshold)
                changes_applied.append("score_threshold")
                previous_values["score_threshold"] = str(prev)

            # Apply position sizing
            if request.apply_position_sizing:
                prev = await self._get_current_position_sizing()
                await self._apply_position_sizing(config.position_sizing)
                changes_applied.append("position_sizing")
                previous_values["position_sizing"] = prev

            # Apply exit strategy
            if request.apply_exit_strategy:
                prev = await self._get_current_exit_strategy()
                await self._apply_exit_strategy(config.exit_strategy)
                changes_applied.append("exit_strategy")
                previous_values["exit_strategy"] = prev

            logger.info(
                "backtest_settings_applied",
                backtest_id=request.backtest_id,
                changes=changes_applied,
            )

            return ApplySettingsResult(
                success=True,
                backtest_id=request.backtest_id,
                applied_at=datetime.now(UTC),
                changes_applied=changes_applied,
                previous_values=previous_values,
            )

        except Exception as e:
            logger.error("failed_to_apply_settings", error=str(e))
            return ApplySettingsResult(
                success=False,
                backtest_id=request.backtest_id,
                applied_at=datetime.now(UTC),
                error_message=str(e),
            )

    async def _get_current_weights(self) -> dict:
        """Get current scoring weights."""
        supabase = await self._get_supabase()
        response = (
            await supabase.table("scoring_weights")
            .select("*")
            .eq("is_active", True)
            .single()
            .execute()
        )
        return response.data if response.data else {}

    async def _apply_scoring_weights(self, weights: ScoringWeights):
        """Apply new scoring weights."""
        supabase = await self._get_supabase()

        # Deactivate current weights
        await supabase.table("scoring_weights").update({"is_active": False}).eq(
            "is_active", True
        ).execute()

        # Insert new weights
        await supabase.table("scoring_weights").insert(
            {
                "wallet_score_weight": float(weights.wallet_score_weight),
                "token_metrics_weight": float(weights.token_metrics_weight),
                "liquidity_weight": float(weights.liquidity_weight),
                "holder_distribution_weight": float(weights.holder_distribution_weight),
                "momentum_weight": float(weights.momentum_weight),
                "is_active": True,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ).execute()

    async def _get_current_threshold(self) -> Decimal:
        """Get current score threshold."""
        supabase = await self._get_supabase()
        response = (
            await supabase.table("system_config")
            .select("value")
            .eq("key", "score_threshold")
            .single()
            .execute()
        )
        return Decimal(str(response.data["value"])) if response.data else Decimal("70")

    async def _apply_threshold(self, threshold: Decimal):
        """Apply new score threshold."""
        supabase = await self._get_supabase()
        await supabase.table("system_config").upsert(
            {
                "key": "score_threshold",
                "value": float(threshold),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).execute()

    async def _get_current_position_sizing(self) -> dict:
        """Get current position sizing config."""
        supabase = await self._get_supabase()
        response = (
            await supabase.table("system_config")
            .select("value")
            .eq("key", "position_sizing")
            .single()
            .execute()
        )
        return response.data["value"] if response.data else {}

    async def _apply_position_sizing(self, config):
        """Apply new position sizing config."""
        supabase = await self._get_supabase()
        await supabase.table("system_config").upsert(
            {
                "key": "position_sizing",
                "value": config.model_dump(mode="json"),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).execute()

    async def _get_current_exit_strategy(self) -> dict:
        """Get current exit strategy config."""
        supabase = await self._get_supabase()
        response = (
            await supabase.table("system_config")
            .select("value")
            .eq("key", "exit_strategy")
            .single()
            .execute()
        )
        return response.data["value"] if response.data else {}

    async def _apply_exit_strategy(self, config):
        """Apply new exit strategy config."""
        supabase = await self._get_supabase()
        await supabase.table("system_config").upsert(
            {
                "key": "exit_strategy",
                "value": config.model_dump(mode="json"),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).execute()

    def get_progress(self, backtest_id: str) -> BacktestProgress | None:
        """Get progress of a running backtest."""
        return self._running_backtests.get(backtest_id)

    def clear_cache(self):
        """Clear the signal cache."""
        self._signal_cache.clear()
        logger.info("backtest_signal_cache_cleared")


# Singleton instance
_backtest_service: BacktestService | None = None


async def get_backtest_service() -> BacktestService:
    """Get the singleton backtest service instance."""
    global _backtest_service
    if _backtest_service is None:
        _backtest_service = BacktestService()
    return _backtest_service
