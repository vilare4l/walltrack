-- Migration: 007_config_rpc_rate_limiting.sql
-- Date: 2026-01-02
-- Story: 3.5.5 - Global Rate Limiter Discovery Worker
-- Description: Add RPC rate limiting configuration parameters
--
-- These parameters control RPC request rates to avoid 429 rate limiting
-- from Solana public RPC endpoint (40 req/10s = 4 req/sec limit).
--
-- Based on empirical testing (scripts/test_rpc_limits.py):
-- - Actual limit: ~2-3 requests before 429 error
-- - Recommended: 1 req/sec (1000ms delay) for safety
-- - Light scenario: 20 tx/wallet = ~9 min for 52 wallets

-- RPC Rate Limiting Parameters
INSERT INTO walltrack.config (key, value, category, description) VALUES
(
    'profiling_signatures_limit',
    '20',
    'rpc_rate_limiting',
    'Max signatures to fetch per wallet (reduces RPC calls). Default: 20 (Light scenario). Range: 10-100.'
),
(
    'profiling_transactions_limit',
    '20',
    'rpc_rate_limiting',
    'Max transactions to fetch per wallet (reduces RPC calls). Default: 20 (Light scenario). Range: 10-100.'
),
(
    'profiling_rpc_delay_ms',
    '1000',
    'rpc_rate_limiting',
    'Delay in milliseconds between RPC calls (global rate limiter). Default: 1000ms (1 req/sec). Increase if getting 429 errors.'
),
(
    'profiling_wallet_delay_seconds',
    '10',
    'rpc_rate_limiting',
    'Delay in seconds between processing each wallet. Default: 10s. Adds safety margin on top of RPC delay.'
),
(
    'profiling_batch_size',
    '10',
    'rpc_rate_limiting',
    'Max wallets to process per polling cycle. Default: 10. Prevents worker from running too long.'
)
ON CONFLICT (key) DO NOTHING;

-- Rollback (commented)
-- DELETE FROM walltrack.config WHERE category = 'rpc_rate_limiting';
