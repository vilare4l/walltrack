# Epic 2: Smart Money Discovery & Token Safety

Operator can discover smart money wallets via GMGN, add them to watchlist, receive real-time swap signals via Helius webhooks, and automatically filter unsafe tokens before any positions are created.

### Story 2.1: Watchlist CRUD Operations - Add, Edit, Remove Wallets

As an operator,
I want to manually add, edit, and remove wallet addresses from my watchlist,
So that I can curate my list of smart money wallets to monitor.

**Acceptance Criteria:**

**Given** I am on the Watchlist tab
**When** I click the [+ Add Wallet] button
**Then** a modal form appears with fields: Wallet Address (required), Label (optional), Mode (dropdown: Simulation/Live, default: Simulation), Initial Win Rate % (number), Initial Trades Observed (number), Initial PnL USD (number)
**And** the form has [Save] and [Cancel] buttons

**Given** the Add Wallet modal is open
**When** I enter a valid Solana wallet address (58 characters, base58) and click [Save]
**Then** the wallet is inserted into the `wallets` table with status='active', helius_sync_status='pending'
**And** the modal closes
**And** the wallets table refreshes showing the new wallet
**And** a success message displays: "Wallet added successfully"

**Given** the Add Wallet modal is open
**When** I enter an invalid wallet address and click [Save]
**Then** a validation error displays: "Invalid Solana address format"
**And** the form does not submit
**And** the modal remains open for correction

**Given** I have a wallet in my watchlist
**When** I click on the wallet row in the table and then click [Edit] in the sidebar
**Then** an Edit Wallet modal appears pre-filled with the wallet's current data
**And** I can modify: Label, Mode, Initial metrics
**And** I cannot modify: Wallet Address (read-only)

**Given** the Edit Wallet modal is open with modified data
**When** I click [Save]
**Then** the wallet record is updated in the `wallets` table
**And** the modal closes
**And** the wallets table refreshes showing the updated data
**And** a success message displays: "Wallet updated successfully"

**Given** I have a wallet in my watchlist
**When** I click on the wallet row and then click [Remove Wallet] in the sidebar
**Then** a confirmation dialog appears: "Are you sure you want to remove this wallet? This action cannot be undone."
**And** the dialog has [Confirm] and [Cancel] buttons

**Given** the Remove Wallet confirmation dialog is open
**When** I click [Confirm]
**Then** the wallet record is deleted from the `wallets` table (hard delete or status='deleted')
**And** the dialog closes
**And** the wallets table refreshes without the deleted wallet
**And** a success message displays: "Wallet removed successfully"

### Story 2.2: Helius Webhook Registration & Global Address Monitoring

As an operator,
I want Helius to monitor all my active watchlist wallets via a global webhook,
So that I receive real-time swap notifications for all tracked addresses.

**Acceptance Criteria:**

**Given** the system is configured with a valid HELIUS_API_KEY in .env
**When** the application starts
**Then** a background worker initializes and checks if a global webhook exists in the `config` table
**And** if no webhook exists, the worker calls Helius API to create a new webhook with type='enhanced' and transactionTypes=['SWAP']
**And** the webhook URL is set to the application's public endpoint (e.g., https://walltrack.app/webhooks/helius)
**And** the webhook_id is stored in `config.helius_webhook_id`

**Given** a global Helius webhook is registered
**When** a new wallet is added to the watchlist (status='active')
**Then** a background sync worker triggers within 30 seconds
**And** the worker retrieves all active wallet addresses from the `wallets` table
**And** the worker calls Helius API to update the webhook's accountAddresses list with all active addresses
**And** the wallet's `helius_synced_at` timestamp is updated
**And** the wallet's `helius_sync_status` is set to 'synced'

**Given** multiple wallets are added/removed/deactivated within 5 minutes
**When** the scheduled batch sync runs (every 5 minutes)
**Then** all address list changes are batched into a single Helius API call
**And** the webhook's accountAddresses list is updated once with the complete active wallet list
**And** all affected wallets have their `helius_synced_at` and `helius_sync_status` updated

**Given** the Helius webhook sync fails (API error, network issue)
**When** the sync worker encounters the error
**Then** the error is logged with structured logging (level: ERROR, context: webhook_sync)
**And** the affected wallets have `helius_sync_status` set to 'failed'
**And** the worker retries the sync after exponential backoff (1min, 2min, 5min)

**Given** I am on the Config tab in the API Keys section
**When** I view the webhook status indicator
**Then** it displays "Connected ✅" if the webhook is registered and responding
**And** it displays "Disconnected ❌" if the webhook registration failed or is inactive
**And** the last sync timestamp is shown (e.g., "Last synced: 3 minutes ago")

### Story 2.3: Webhook Signal Reception & Storage

As an operator,
I want all swap signals from Helius webhooks to be captured and stored,
So that I have a complete audit trail of all detected trading activity.

**Acceptance Criteria:**

**Given** the Helius webhook is registered and monitoring active wallets
**When** a monitored wallet executes a SWAP transaction on Solana
**Then** Helius sends a POST request to the webhook endpoint with transaction details
**And** the webhook handler receives: transaction signature, wallet address, token mint addresses (input/output), amounts, timestamp

**Given** the webhook handler receives a valid swap signal
**When** the signal is processed
**Then** a new record is inserted into the `signals` table with: source_wallet_address, token_mint (output token), amount_usd (estimated), detected_at (timestamp), filtered=false, filter_reason=null, raw_webhook_data (JSONB)
**And** the signal is logged with structured logging (level: INFO, event: signal_received)

**Given** the webhook handler receives a duplicate signal (same tx_signature)
**When** the signal is processed
**Then** the duplicate is detected by checking existing `signals.raw_webhook_data->>'signature'`
**And** a new record is still inserted with filtered=true, filter_reason='duplicate_signal'
**And** the duplicate is logged with structured logging (level: WARN, event: duplicate_signal)

**Given** the webhook handler receives an invalid or malformed payload
**When** the signal is processed
**Then** the handler logs the error with structured logging (level: ERROR, event: invalid_webhook_payload, payload: truncated_data)
**And** the handler returns HTTP 400 Bad Request to Helius
**And** no signal record is created in the database

**Given** signals are being stored in the `signals` table
**When** I view the Dashboard tab
**Then** the last signal timestamp is displayed in the performance metrics area
**And** the timestamp updates in real-time (or near real-time with <1min delay) as new signals arrive

**Given** I am viewing the Watchlist tab wallet sidebar
**When** I click on a wallet row
**Then** the sidebar displays "Recent Signals" showing the last 5 signals for that wallet
**And** each signal shows: Token symbol, Amount USD, Timestamp (relative, e.g., "2 minutes ago"), Filtered status (Yes/No)

### Story 2.4: Token Safety Analysis - Multi-Source Scoring

As an operator,
I want tokens to be automatically analyzed for safety risks using multiple data sources,
So that I avoid creating positions on rug pulls or honeypots.

**Acceptance Criteria:**

**Given** a new signal is received and stored in the `signals` table
**When** the signal processing pipeline checks the token_mint
**Then** the system queries the `tokens` table for an existing safety analysis
**And** if the token exists and `analyzed_at` is < 1 hour old, the cached score is used
**And** if the token does not exist or cache is stale, a new analysis is triggered

**Given** a token requires safety analysis
**When** the analysis worker executes
**Then** the worker attempts to fetch data from RugCheck API (primary source)
**And** if RugCheck returns valid data, the worker calculates 4 check scores:
- Liquidity Check: ≥$50K = 1.0, <$50K = 0.0
- Holder Distribution: Top 10 holders < 80% = 1.0, ≥80% = 0.0
- Contract Analysis: No honeypot flags = 1.0, honeypot detected = 0.0
- Age Check: ≥24h = 1.0, <24h = 0.0
**And** the overall safety_score is calculated as weighted average: (Liquidity * 0.25) + (Holder * 0.25) + (Contract * 0.25) + (Age * 0.25)

**Given** RugCheck API fails or returns incomplete data
**When** the analysis worker detects the failure
**Then** the worker falls back to Helius Metadata API (secondary source)
**And** if Helius returns valid data, partial scoring is performed (e.g., only Liquidity + Age, missing Contract/Holder checks)
**And** the safety_score is calculated with available checks weighted proportionally

**Given** both RugCheck and Helius APIs fail
**When** the analysis worker detects the failure
**Then** the worker falls back to DexScreener API (tertiary source)
**And** if DexScreener returns valid data, minimal scoring is performed (Liquidity + basic metadata)
**And** the safety_score is calculated with available data

**Given** all three data sources fail (RugCheck, Helius, DexScreener)
**When** the analysis worker exhausts all retries
**Then** the token is inserted into `tokens` table with safety_score=0.0, data_source='none', analyzed_at=NOW()
**And** the failure is logged with structured logging (level: ERROR, event: token_analysis_failed, token_mint: address)

**Given** a token safety analysis completes successfully
**When** the analysis result is ready
**Then** a record is inserted/updated in the `tokens` table with: token_mint (PK), safety_score (0.0-1.0), analyzed_at (timestamp), data_source (rugcheck/helius/dexscreener), metadata (JSONB with raw API response)
**And** the success is logged with structured logging (level: INFO, event: token_analyzed, safety_score: value)

**Given** I am viewing token data in the Dashboard sidebar (position details)
**When** I click on a position row
**Then** the sidebar displays the token's safety score (e.g., "Safety Score: 0.75/1.00")
**And** the score is color-coded: Green (≥0.60), Yellow (0.40-0.59), Red (<0.40)
**And** the data source is indicated (e.g., "Source: RugCheck")

### Story 2.5: Signal Filtering Logic & Audit Trail

As an operator,
I want signals for unsafe tokens to be automatically filtered out,
So that positions are only created for tokens meeting my safety threshold.

**Acceptance Criteria:**

**Given** a signal has been received and the token safety analysis is complete
**When** the signal filtering logic executes
**Then** the system retrieves the safety threshold from the `config` table (default: 0.60)
**And** the system compares the token's `safety_score` against the threshold

**Given** a token's safety_score is ≥ the threshold (e.g., 0.75 ≥ 0.60)
**When** the filtering logic evaluates the signal
**Then** the signal record is updated with filtered=false, filter_reason=null
**And** the signal is marked as ready for position creation
**And** the approval is logged with structured logging (level: INFO, event: signal_approved, safety_score: value)

**Given** a token's safety_score is < the threshold (e.g., 0.45 < 0.60)
**When** the filtering logic evaluates the signal
**Then** the signal record is updated with filtered=true, filter_reason='safety_score_below_threshold'
**And** the signal is NOT forwarded to the position creation pipeline
**And** the rejection is logged with structured logging (level: WARN, event: signal_filtered, safety_score: value, threshold: value)

**Given** signals are being filtered automatically
**When** I view the Watchlist tab wallet sidebar
**Then** the "Recent Signals" section shows filtered signals with a visual indicator (e.g., 🚫 icon or strikethrough)
**And** I can see the filter_reason for each filtered signal (e.g., "Filtered: Safety score below threshold")

**Given** I want to audit why signals were filtered
**When** I query the `signals` table (via admin tools or future reporting feature)
**Then** I can filter by filtered=true and view all rejected signals with their filter_reason
**And** I can analyze filtering patterns (e.g., "50% of signals filtered due to low liquidity")

**Given** I am on the Config tab in the Risk Limits section
**When** I view the Safety Threshold field
**Then** the current threshold is displayed (e.g., 0.60)
**And** I can adjust the threshold value (range: 0.00 to 1.00)
**And** saving the new threshold updates the `config` table
**And** future signals use the updated threshold immediately
