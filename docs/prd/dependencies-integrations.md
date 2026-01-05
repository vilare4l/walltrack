# Dependencies & Integrations

### External Dependencies

**Critical (System Cannot Function Without):**
- Helius API (webhooks for signal detection and wallet monitoring)
- Jupiter API (swap execution in live mode)
- DexScreener API (price monitoring for exit strategies)
- Supabase (data persistence)

**Optional (Enhances Functionality):**
- GMGN (manual wallet discovery - external tool, not integrated)

### Integration Points

**Helius Webhooks:**
- **Integration Type:** Event-driven webhooks
- **Data Flow:** Helius → WallTrack webhook endpoint → Signal processing pipeline
- **Error Handling:** Retry on transient failures, log webhook failures, alert if no signals for 48h
- **SLA Impact:** Webhook downtime = missed signals = missed trades

**Jupiter API:**
- **Integration Type:** REST API (synchronous swap execution)
- **Data Flow:** WallTrack → Jupiter quote API → Jupiter swap API → Transaction confirmation
- **Error Handling:** Retry on transient failures, abort on critical errors (insufficient funds, invalid token), log all failures
- **SLA Impact:** API downtime = cannot execute live trades (simulation mode unaffected)

**DexScreener API:**
- **Integration Type:** REST API (polling)
- **Data Flow:** WallTrack → DexScreener price endpoint → Price update → Exit strategy evaluation
- **Error Handling:** Retry on transient failures, use last known price if API unavailable, alert if stale data >5 minutes
- **SLA Impact:** API downtime = delayed exit triggers (stop-loss/trailing-stop may not execute on time)

**Supabase:**
- **Integration Type:** PostgreSQL database (client library)
- **Data Flow:** WallTrack → Supabase client → PostgreSQL
- **Error Handling:** Connection pooling, retry on transient failures, log database errors
- **SLA Impact:** Database downtime = system inoperable (no state persistence)
