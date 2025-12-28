"""Contextual sidebar component for drill-down details."""

from typing import Any

import gradio as gr


def render_empty_context() -> str:
    """Render empty context placeholder."""
    return """
### No Selection

Click on any row in a table to view details here.

**Available drill-down:**
- Positions: Token info, entry details, exit strategy
- Wallets: Metrics, discovery source, cluster membership
- Signals: Score breakdown, source wallet, token info
- Clusters: Members, leader, cohesion metrics
"""


def render_position_context(position: dict[str, Any]) -> str:
    """Render position context for sidebar.

    Args:
        position: Position data dict

    Returns:
        Markdown content for sidebar
    """
    token = position.get("token_symbol") or position.get("token_address", "")[:12]
    pnl_pct = position.get("pnl_pct", 0)
    pnl_color = "green" if pnl_pct >= 0 else "red"

    return f"""
### {token}

**Status:** {position.get("status", "open")}

---

#### Entry
| Metric | Value |
|--------|-------|
| Price | {position.get("entry_price", 0):.8f} |
| Amount | {position.get("entry_amount_sol", 0):.4f} SOL |
| Time | {position.get("entry_time", "N/A")} |

---

#### Current
| Metric | Value |
|--------|-------|
| Price | {position.get("current_price", 0):.8f} |
| P&L | <span style="color:{pnl_color}">{pnl_pct:+.1f}%</span> |
| Multiplier | x{position.get("multiplier", 1.0):.2f} |

---

#### Exit Strategy
**Strategy:** {position.get("exit_strategy_id", "default")}

| Level | Trigger | Status |
|-------|---------|--------|
| Stop Loss | {position.get("stop_loss_price", "N/A")} | - |
| Take Profit | {position.get("take_profit_price", "N/A")} | - |

---

#### Source
**Wallet:** `{position.get("source_wallet", "N/A")[:16]}...`
**Signal Score:** {position.get("signal_score", 0):.2f}
"""


def render_wallet_context(wallet: dict[str, Any]) -> str:
    """Render wallet context for sidebar.

    Args:
        wallet: Wallet data dict

    Returns:
        Markdown content for sidebar
    """
    address = wallet.get("address", "")
    profile = wallet.get("profile", {})
    status = wallet.get("status", "active")

    status_emoji = {
        "active": "🟢",
        "decay_detected": "🟡",
        "blacklisted": "🔴",
        "insufficient_data": "⚪",
    }.get(status, "⚪")

    return f"""
### Wallet Details

**Address:** `{address[:20]}...`

**Status:** {status_emoji} {status}

**Score:** {wallet.get("score", 0):.2%}

---

#### Performance
| Metric | Value |
|--------|-------|
| Win Rate | {profile.get("win_rate", 0):.1%} |
| Total PnL | {profile.get("total_pnl", 0):.2f} SOL |
| Avg PnL/Trade | {profile.get("avg_pnl_per_trade", 0):.4f} SOL |
| Total Trades | {profile.get("total_trades", 0)} |
| Avg Hold Time | {profile.get("avg_hold_time_hours", 0):.1f}h |

---

#### Discovery
| Info | Value |
|------|-------|
| Discovered | {wallet.get("discovered_at", "N/A")[:10] if wallet.get("discovered_at") else "N/A"} |
| Discovery Count | {wallet.get("discovery_count", 0)} |
| Last Signal | {(wallet.get("last_signal_at") or "Never")[:10]} |

---

#### Cluster
**Cluster ID:** {wallet.get("cluster_id", "None")}
**Is Leader:** {"Yes" if wallet.get("is_leader") else "No"}
"""


def render_signal_context(signal: dict[str, Any]) -> str:
    """Render signal context for sidebar.

    Args:
        signal: Signal data dict

    Returns:
        Markdown content for sidebar
    """
    score = signal.get("score", 0)
    score_color = "green" if score >= 0.85 else "orange" if score >= 0.70 else "red"

    return f"""
### Signal Details

**Token:** `{signal.get("token_address", "")[:16]}...`

**Time:** {signal.get("timestamp", "N/A")}

---

#### Score Breakdown

**Final Score:** <span style="color:{score_color}">{score:.3f}</span>

| Factor | Score | Weight | Contribution |
|--------|-------|--------|--------------|
| Wallet | {signal.get("wallet_score", 0):.3f} | 30% | {signal.get("wallet_score", 0)*0.3:.3f} |
| Cluster | {signal.get("cluster_score", 0):.3f} | 25% | {signal.get("cluster_score", 0)*0.25:.3f} |
| Token | {signal.get("token_score", 0):.3f} | 25% | {signal.get("token_score", 0)*0.25:.3f} |
| Context | {signal.get("context_score", 0):.3f} | 20% | {signal.get("context_score", 0)*0.2:.3f} |

---

#### Source Wallet
**Address:** `{signal.get("wallet_address", "")[:16]}...`
**Wallet Score:** {signal.get("wallet_score", 0):.2f}

---

#### Action
**Status:** {signal.get("action_status", "pending")}
**Trade ID:** {signal.get("trade_id", "N/A")}
"""


def render_cluster_context(cluster: dict[str, Any]) -> str:
    """Render cluster context for sidebar.

    Args:
        cluster: Cluster data dict

    Returns:
        Markdown content for sidebar
    """
    members = cluster.get("members", [])
    leader = cluster.get("leader_address")

    member_list = "\n".join(
        f"- `{m.get('wallet_address', '')[:16]}...`"
        for m in members[:5]
    )
    if len(members) > 5:
        member_list += f"\n- ... and {len(members) - 5} more"

    return f"""
### Cluster Details

**ID:** `{cluster.get("id", "")[:16]}...`

---

#### Metrics
| Metric | Value |
|--------|-------|
| Size | {cluster.get("size", 0)} wallets |
| Cohesion | {cluster.get("cohesion_score", 0):.2f} |
| Signal Multiplier | {cluster.get("signal_multiplier", 1.0):.2f}x |

---

#### Leader
**Address:** `{leader[:20] if leader else "None"}...`
**Leader Score:** {cluster.get("leader_score", 0):.2f}

---

#### Members
{member_list}

---

#### Relationships
| Type | Count |
|------|-------|
| FUNDED_BY | {cluster.get("funded_by_count", 0)} |
| BUYS_WITH | {cluster.get("buys_with_count", 0)} |
| CO_OCCURS | {cluster.get("co_occurs_count", 0)} |
"""


def create_sidebar_state() -> gr.State:
    """Create state for tracking selected entity."""
    return gr.State(value={"type": None, "data": None})


def update_sidebar_content(state: dict[str, Any]) -> str:
    """Update sidebar content based on selected entity.

    Args:
        state: Current sidebar state with type and data

    Returns:
        Markdown content for sidebar
    """
    if not state or not state.get("type"):
        return render_empty_context()

    entity_type = state["type"]
    data = state.get("data", {})

    renderers = {
        "position": render_position_context,
        "wallet": render_wallet_context,
        "signal": render_signal_context,
        "cluster": render_cluster_context,
    }

    renderer = renderers.get(entity_type)
    if renderer:
        return renderer(data)

    return render_empty_context()
