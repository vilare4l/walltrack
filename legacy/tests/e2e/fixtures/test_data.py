"""E2E test data fixtures for seeding and cleanup.

This module provides test data that can be used to populate the database
for comprehensive E2E testing. Data is designed to cover all UI scenarios.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

# =============================================================================
# Test Wallet Data
# =============================================================================

TEST_WALLETS = [
    {
        "address": "TestWallet1AAA111222333444555666777888999",
        "status": "active",
        "score": 0.85,
        "win_rate": 0.72,
        "total_pnl": 450.5,
        "trade_count": 28,
        "discovery_count": 3,
        "discovery_source": "manual",
        "discovery_tokens": ["TokenA", "TokenB"],
        "cluster_id": "cluster-001",
    },
    {
        "address": "TestWallet2BBB111222333444555666777888999",
        "status": "active",
        "score": 0.78,
        "win_rate": 0.65,
        "total_pnl": 280.3,
        "trade_count": 42,
        "discovery_count": 5,
        "discovery_source": "discovery",
        "discovery_tokens": ["TokenA", "TokenC", "TokenD"],
        "cluster_id": "cluster-001",
    },
    {
        "address": "TestWallet3CCC111222333444555666777888999",
        "status": "blacklisted",
        "score": 0.45,
        "win_rate": 0.35,
        "total_pnl": -120.0,
        "trade_count": 15,
        "discovery_count": 1,
        "discovery_source": "helius",
        "discovery_tokens": ["TokenE"],
        "cluster_id": None,
    },
    {
        "address": "TestWallet4DDD111222333444555666777888999",
        "status": "pending",
        "score": 0.0,
        "win_rate": 0.0,
        "total_pnl": 0.0,
        "trade_count": 0,
        "discovery_count": 1,
        "discovery_source": "manual",
        "discovery_tokens": [],
        "cluster_id": None,
    },
]

# =============================================================================
# Test Position Data
# =============================================================================

def generate_test_positions() -> list[dict[str, Any]]:
    """Generate test positions with various states."""
    now = datetime.utcnow()

    return [
        {
            "id": f"pos-{uuid4().hex[:8]}",
            "token_address": "TestTokenSOL111222333444555666777888999",
            "token_symbol": "TESTSOL",
            "entry_price": 0.0025,
            "current_price": 0.0032,
            "entry_time": (now - timedelta(hours=2)).isoformat(),
            "exit_time": None,
            "status": "open",
            "pnl_pct": 28.0,
            "pnl_sol": 0.14,
            "size_sol": 0.5,
            "exit_strategy_name": "Standard Exit",
            "wallet_address": TEST_WALLETS[0]["address"],
        },
        {
            "id": f"pos-{uuid4().hex[:8]}",
            "token_address": "TestTokenMEME111222333444555666777888",
            "token_symbol": "MEME",
            "entry_price": 0.00015,
            "current_price": 0.00012,
            "entry_time": (now - timedelta(hours=5)).isoformat(),
            "exit_time": None,
            "status": "open",
            "pnl_pct": -20.0,
            "pnl_sol": -0.06,
            "size_sol": 0.3,
            "exit_strategy_name": "Conservative",
            "wallet_address": TEST_WALLETS[1]["address"],
        },
        {
            "id": f"pos-{uuid4().hex[:8]}",
            "token_address": "TestTokenWIN111222333444555666777888",
            "token_symbol": "WIN",
            "entry_price": 0.001,
            "current_price": None,
            "exit_price": 0.0025,
            "entry_time": (now - timedelta(days=1)).isoformat(),
            "exit_time": (now - timedelta(hours=12)).isoformat(),
            "status": "closed",
            "pnl_pct": 150.0,
            "pnl_sol": 0.75,
            "size_sol": 0.5,
            "exit_strategy_name": "Aggressive",
            "wallet_address": TEST_WALLETS[0]["address"],
        },
    ]

TEST_POSITIONS = generate_test_positions()

# =============================================================================
# Test Order Data
# =============================================================================

def generate_test_orders() -> list[dict[str, Any]]:
    """Generate test orders with various statuses."""
    now = datetime.utcnow()

    return [
        {
            "id": f"ord-{uuid4().hex[:8]}",
            "type": "BUY",
            "token_address": "TestTokenSOL111222333444555666777888999",
            "token_symbol": "TESTSOL",
            "amount_sol": 0.5,
            "status": "filled",
            "attempts": 1,
            "created_at": (now - timedelta(hours=3)).isoformat(),
            "updated_at": (now - timedelta(hours=3)).isoformat(),
            "position_id": TEST_POSITIONS[0]["id"],
        },
        {
            "id": f"ord-{uuid4().hex[:8]}",
            "type": "BUY",
            "token_address": "TestTokenMEME111222333444555666777888",
            "token_symbol": "MEME",
            "amount_sol": 0.3,
            "status": "filled",
            "attempts": 2,
            "created_at": (now - timedelta(hours=6)).isoformat(),
            "updated_at": (now - timedelta(hours=5, minutes=30)).isoformat(),
            "position_id": TEST_POSITIONS[1]["id"],
        },
        {
            "id": f"ord-{uuid4().hex[:8]}",
            "type": "SELL",
            "token_address": "TestTokenNEW111222333444555666777888",
            "token_symbol": "NEW",
            "amount_sol": 0.25,
            "status": "pending",
            "attempts": 0,
            "created_at": (now - timedelta(minutes=5)).isoformat(),
            "updated_at": (now - timedelta(minutes=5)).isoformat(),
            "position_id": None,
        },
        {
            "id": f"ord-{uuid4().hex[:8]}",
            "type": "BUY",
            "token_address": "TestTokenFAIL111222333444555666777888",
            "token_symbol": "FAIL",
            "amount_sol": 0.4,
            "status": "failed",
            "attempts": 3,
            "error_message": "Insufficient liquidity",
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "updated_at": (now - timedelta(minutes=45)).isoformat(),
            "position_id": None,
        },
    ]

TEST_ORDERS = generate_test_orders()

# =============================================================================
# Test Signal Data
# =============================================================================

def generate_test_signals() -> list[dict[str, Any]]:
    """Generate test signals for the signal feed."""
    now = datetime.utcnow()

    return [
        {
            "id": f"sig-{uuid4().hex[:8]}",
            "timestamp": (now - timedelta(minutes=15)).isoformat(),
            "token_address": "TestTokenHOT111222333444555666777888999",
            "token_symbol": "HOT",
            "wallet_address": TEST_WALLETS[0]["address"],
            "wallet_score": 0.85,
            "cluster_boost": 1.15,
            "final_score": 0.92,
            "amount_sol": 1.5,
            "signal_type": "BUY",
            "trade_decision": True,
        },
        {
            "id": f"sig-{uuid4().hex[:8]}",
            "timestamp": (now - timedelta(minutes=45)).isoformat(),
            "token_address": "TestTokenCOLD111222333444555666777888999",
            "token_symbol": "COLD",
            "wallet_address": TEST_WALLETS[1]["address"],
            "wallet_score": 0.78,
            "cluster_boost": 1.0,
            "final_score": 0.58,
            "amount_sol": 0.8,
            "signal_type": "BUY",
            "trade_decision": False,
        },
        {
            "id": f"sig-{uuid4().hex[:8]}",
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "token_address": "TestTokenMID111222333444555666777888999",
            "token_symbol": "MID",
            "wallet_address": TEST_WALLETS[0]["address"],
            "wallet_score": 0.85,
            "cluster_boost": 1.25,
            "final_score": 0.88,
            "amount_sol": 2.0,
            "signal_type": "BUY",
            "trade_decision": True,
        },
    ]

TEST_SIGNALS = generate_test_signals()

# =============================================================================
# Test Cluster Data
# =============================================================================

TEST_CLUSTERS = [
    {
        "id": "cluster-001",
        "size": 5,
        "cohesion": 0.82,
        "multiplier": 1.25,
        "leader_address": TEST_WALLETS[0]["address"],
        "member_addresses": [
            TEST_WALLETS[0]["address"],
            TEST_WALLETS[1]["address"],
            "OtherWallet1AAA111222333444555666777888999",
            "OtherWallet2BBB111222333444555666777888999",
            "OtherWallet3CCC111222333444555666777888999",
        ],
        "created_at": (datetime.utcnow() - timedelta(days=7)).isoformat(),
    },
    {
        "id": "cluster-002",
        "size": 3,
        "cohesion": 0.68,
        "multiplier": 1.1,
        "leader_address": None,
        "member_addresses": [
            "ClusterBWallet1AAA111222333444555666777888999",
            "ClusterBWallet2BBB111222333444555666777888999",
            "ClusterBWallet3CCC111222333444555666777888999",
        ],
        "created_at": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    },
]

# =============================================================================
# Test Exit Strategy Data
# =============================================================================

TEST_EXIT_STRATEGIES = [
    {
        "id": f"strat-{uuid4().hex[:8]}",
        "name": "Standard Exit",
        "version": 1,
        "status": "active",
        "description": "Balanced risk/reward exit strategy",
        "max_hold_hours": 24,
        "stagnation_hours": 6,
        "stagnation_threshold_pct": 2.0,
        "rules": [
            {"rule_type": "stop_loss", "trigger_pct": -15, "exit_pct": 100, "priority": 0, "enabled": True},
            {"rule_type": "take_profit", "trigger_pct": 25, "exit_pct": 50, "priority": 1, "enabled": True},
            {"rule_type": "trailing_stop", "trigger_pct": -8, "exit_pct": 100, "priority": 2, "enabled": True, "params": {"activation_pct": 20}},
        ],
        "created_at": (datetime.utcnow() - timedelta(days=30)).isoformat(),
    },
    {
        "id": f"strat-{uuid4().hex[:8]}",
        "name": "Conservative",
        "version": 2,
        "status": "active",
        "description": "Lower risk exit strategy for volatile markets",
        "max_hold_hours": 12,
        "stagnation_hours": 4,
        "stagnation_threshold_pct": 1.5,
        "rules": [
            {"rule_type": "stop_loss", "trigger_pct": -10, "exit_pct": 100, "priority": 0, "enabled": True},
            {"rule_type": "take_profit", "trigger_pct": 15, "exit_pct": 75, "priority": 1, "enabled": True},
        ],
        "created_at": (datetime.utcnow() - timedelta(days=14)).isoformat(),
    },
    {
        "id": f"strat-{uuid4().hex[:8]}",
        "name": "Aggressive",
        "version": 1,
        "status": "draft",
        "description": "High risk/reward strategy",
        "max_hold_hours": 48,
        "stagnation_hours": 12,
        "stagnation_threshold_pct": 5.0,
        "rules": [
            {"rule_type": "stop_loss", "trigger_pct": -25, "exit_pct": 100, "priority": 0, "enabled": True},
            {"rule_type": "take_profit", "trigger_pct": 50, "exit_pct": 30, "priority": 1, "enabled": True},
            {"rule_type": "take_profit", "trigger_pct": 100, "exit_pct": 50, "priority": 2, "enabled": True},
        ],
        "created_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
    },
]

# =============================================================================
# Test Config Data
# =============================================================================

TEST_CONFIG = {
    "version": 5,
    "status": "active",
    "trading": {
        "base_position_pct": 2.0,
        "max_position_sol": 1.0,
        "min_position_sol": 0.1,
        "sizing_mode": "risk_based",
        "risk_per_trade_pct": 1.5,
        "high_conviction_multiplier": 1.5,
        "score_threshold": 0.65,
        "high_conviction_threshold": 0.85,
        "max_concurrent_positions": 10,
        "daily_loss_limit_pct": 5.0,
        "daily_loss_limit_enabled": True,
        "max_token_pct": 20.0,
        "max_cluster_pct": 40.0,
        "max_positions_per_cluster": 3,
        "entry_slippage_bps": 100,
        "exit_slippage_bps": 150,
    },
    "scoring": {
        "wallet_weight": 0.6,
        "cluster_weight": 0.4,
        "min_wallet_score": 0.3,
        "min_cluster_boost": 1.0,
        "max_cluster_boost": 2.0,
    },
    "discovery": {
        "early_window_minutes": 30,
        "min_profit_pct": 50.0,
        "max_wallets_per_token": 100,
        "auto_profile": True,
    },
    "last_updated": datetime.utcnow().isoformat(),
}

# =============================================================================
# Test Alerts Data
# =============================================================================

def generate_test_alerts() -> list[dict[str, Any]]:
    """Generate test alerts for the alerts section."""
    now = datetime.utcnow()

    return [
        {
            "id": f"alert-{uuid4().hex[:8]}",
            "type": "signal",
            "severity": "info",
            "message": "New high-score signal detected: TESTSOL (0.92)",
            "timestamp": (now - timedelta(minutes=5)).isoformat(),
            "read": False,
        },
        {
            "id": f"alert-{uuid4().hex[:8]}",
            "type": "position",
            "severity": "warning",
            "message": "Position MEME approaching stop loss (-20%)",
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "read": False,
        },
        {
            "id": f"alert-{uuid4().hex[:8]}",
            "type": "order",
            "severity": "error",
            "message": "Order failed: FAIL - Insufficient liquidity",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "read": True,
        },
        {
            "id": f"alert-{uuid4().hex[:8]}",
            "type": "system",
            "severity": "success",
            "message": "Cluster analysis completed: 2 new clusters detected",
            "timestamp": (now - timedelta(hours=3)).isoformat(),
            "read": True,
        },
    ]

TEST_ALERTS = generate_test_alerts()
