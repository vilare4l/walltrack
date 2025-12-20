-- Migration: 006_webhook_logs
-- Description: Create webhook_logs table for Helius webhook tracking
-- Epic: 3 - Real-Time Signal Processing & Scoring
-- Story: 3.1 - Helius Webhook Integration

-- Create webhook_logs table
CREATE TABLE IF NOT EXISTS webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_signature VARCHAR(100) NOT NULL UNIQUE,
    wallet_address VARCHAR(50) NOT NULL,
    token_address VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('buy', 'sell')),
    amount_token DECIMAL(30, 10) NOT NULL,
    amount_sol DECIMAL(20, 10) NOT NULL,
    slot BIGINT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ NOT NULL,
    processing_completed_at TIMESTAMPTZ,
    processing_time_ms DECIMAL(10, 2),
    status VARCHAR(20) NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processing', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add comments
COMMENT ON TABLE webhook_logs IS 'Log of received Helius webhook events';
COMMENT ON COLUMN webhook_logs.tx_signature IS 'Solana transaction signature (unique)';
COMMENT ON COLUMN webhook_logs.wallet_address IS 'Wallet that executed the swap';
COMMENT ON COLUMN webhook_logs.token_address IS 'Token mint address involved in swap';
COMMENT ON COLUMN webhook_logs.direction IS 'Swap direction: buy or sell';
COMMENT ON COLUMN webhook_logs.amount_token IS 'Amount of tokens in swap';
COMMENT ON COLUMN webhook_logs.amount_sol IS 'Amount of SOL in swap';
COMMENT ON COLUMN webhook_logs.slot IS 'Solana slot number';
COMMENT ON COLUMN webhook_logs.received_at IS 'When webhook was received by system';
COMMENT ON COLUMN webhook_logs.processing_started_at IS 'When processing began';
COMMENT ON COLUMN webhook_logs.processing_completed_at IS 'When processing completed';
COMMENT ON COLUMN webhook_logs.processing_time_ms IS 'Processing duration in milliseconds';
COMMENT ON COLUMN webhook_logs.status IS 'Processing status: received, processing, completed, failed';
COMMENT ON COLUMN webhook_logs.error_message IS 'Error message if processing failed';

-- Indexes for performance (NFR2: < 500ms processing)
CREATE INDEX IF NOT EXISTS idx_webhook_logs_received_at ON webhook_logs(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_wallet ON webhook_logs(wallet_address);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_token ON webhook_logs(token_address);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_status ON webhook_logs(status);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_slot ON webhook_logs(slot DESC);

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_webhook_logs_wallet_received ON webhook_logs(wallet_address, received_at DESC);

-- Enable Row Level Security
ALTER TABLE webhook_logs ENABLE ROW LEVEL SECURITY;

-- Policy for service role (full access)
CREATE POLICY "Service role has full access to webhook_logs"
    ON webhook_logs
    FOR ALL
    USING (true)
    WITH CHECK (true);
