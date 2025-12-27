-- Story 10.5-14: Alerts table for order failure notifications
-- Tracks system alerts with deduplication and lifecycle management

-- Alerts table
CREATE TABLE IF NOT EXISTS walltrack.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'high', 'critical')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved')),

    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}',

    requires_action BOOLEAN DEFAULT FALSE,
    dedupe_key VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(100),
    resolved_at TIMESTAMPTZ,
    resolution TEXT,
    notified_at TIMESTAMPTZ
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_alerts_status ON walltrack.alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity_status ON walltrack.alerts(severity, status);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON walltrack.alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON walltrack.alerts(alert_type, status);

-- Partial unique index for active alerts with dedupe_key
-- Ensures only one active alert per dedupe_key
CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_dedupe_active
    ON walltrack.alerts(dedupe_key)
    WHERE status = 'active' AND dedupe_key IS NOT NULL;

-- Function to auto-update updated_at
CREATE OR REPLACE FUNCTION walltrack.update_alerts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for auto-updating updated_at
DROP TRIGGER IF EXISTS trigger_alerts_updated_at ON walltrack.alerts;
CREATE TRIGGER trigger_alerts_updated_at
    BEFORE UPDATE ON walltrack.alerts
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_alerts_updated_at();

-- Comment on table
COMMENT ON TABLE walltrack.alerts IS 'System alerts for order failures and other notifications';
COMMENT ON COLUMN walltrack.alerts.dedupe_key IS 'Unique key for deduplication - only one active alert per key';
COMMENT ON COLUMN walltrack.alerts.requires_action IS 'Whether manual user action is required to resolve';
