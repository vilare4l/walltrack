-- ============================================================================
-- Mock Data Insertion Script - Part 2
-- Story 1.1: Database Schema Migration & Mock Data
-- Date: 2026-01-05
-- ============================================================================
--
-- This script inserts mock data for signals, positions, and orders:
-- - 20 signals (10 filtered, 10 processed)
-- - 12 positions (6 open, 6 closed)
-- - 18 orders (12 filled, 4 pending, 2 failed)
-- ============================================================================

-- ============================================================================
-- SIGNALS: 20 signals (10 filtered, 10 processed)
-- ============================================================================

DO $$
DECLARE
    wallet1_addr TEXT := '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU';
    wallet2_addr TEXT := 'DYw8jCTfwHNRJhhmFcbXvVDTqWMEVFBX6ZKUmG5CNSKK';
    wallet3_addr TEXT := 'FwR3PbjS5iyqzLiLugrBqKSa5EKZ4vK2aCPNPdxvNvML';
    wallet4_addr TEXT := 'BonkMAn3jEyPM3AwAv3xqvZ8ys9Z98MPpDRxQwuXiJ9c';
    wallet5_addr TEXT := '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM';

    bonk_addr TEXT := 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263';
    wif_addr TEXT := 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm';
    myro_addr TEXT := 'HhJpBhRRn4g56VsyLuT8DL5Bv31HkXqsrahTTUCZeZg4';
    jto_addr TEXT := 'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL';
    scam_addr TEXT := 'Scam1111111111111111111111111111111111111';
    rug_addr TEXT := 'Rug22222222222222222222222222222222222222';
    pump_addr TEXT := 'Pump3333333333333333333333333333333333333';
    fake_addr TEXT := 'Fake4444444444444444444444444444444444444';
BEGIN
    -- Processed signals (10) - These created positions
    INSERT INTO walltrack.signals (
        id, wallet_address, token_address, signal_type, action,
        amount, price_usd, value_usd,
        processed, processed_at, action_taken,
        received_at, helius_signature
    ) VALUES
    -- Signal 1: Wallet4 (live) buys BONK
    (gen_random_uuid(), wallet4_addr, bonk_addr, 'swap_detected', 'buy',
     5000000, 0.0000125, 62.50,
     true, NOW() - INTERVAL '6 hours', 'position_created',
     NOW() - INTERVAL '6 hours 5 minutes', '5KJ..ABC'),

    -- Signal 2: Wallet4 (live) buys WIF
    (gen_random_uuid(), wallet4_addr, wif_addr, 'swap_detected', 'buy',
     150, 0.850000, 127.50,
     true, NOW() - INTERVAL '5 hours', 'position_created',
     NOW() - INTERVAL '5 hours 3 minutes', '2FH..DEF'),

    -- Signal 3: Wallet5 (live) buys JTO
    (gen_random_uuid(), wallet5_addr, jto_addr, 'swap_detected', 'buy',
     80, 2.150000, 172.00,
     true, NOW() - INTERVAL '4 hours', 'position_created',
     NOW() - INTERVAL '4 hours 2 minutes', '8TG..GHI'),

    -- Signal 4: Wallet1 (simulation) buys MYRO
    (gen_random_uuid(), wallet1_addr, myro_addr, 'swap_detected', 'buy',
     400, 0.320000, 128.00,
     true, NOW() - INTERVAL '3 hours', 'position_created',
     NOW() - INTERVAL '3 hours 1 minute', '3PL..JKL'),

    -- Signal 5: Wallet2 (simulation) buys BONK
    (gen_random_uuid(), wallet2_addr, bonk_addr, 'swap_detected', 'buy',
     8000000, 0.0000120, 96.00,
     true, NOW() - INTERVAL '2 hours 30 minutes', 'position_created',
     NOW() - INTERVAL '2 hours 35 minutes', '9QW..MNO'),

    -- Signal 6: Wallet3 (simulation) buys WIF
    (gen_random_uuid(), wallet3_addr, wif_addr, 'swap_detected', 'buy',
     200, 0.830000, 166.00,
     true, NOW() - INTERVAL '2 hours', 'position_created',
     NOW() - INTERVAL '2 hours 4 minutes', '7RT..PQR'),

    -- Signals 7-10: Closed positions (sells detected)
    (gen_random_uuid(), wallet1_addr, bonk_addr, 'swap_detected', 'buy',
     3000000, 0.0000118, 35.40,
     true, NOW() - INTERVAL '48 hours', 'position_created',
     NOW() - INTERVAL '48 hours 2 minutes', 'XYZ..STU'),
    (gen_random_uuid(), wallet2_addr, myro_addr, 'swap_detected', 'buy',
     500, 0.295000, 147.50,
     true, NOW() - INTERVAL '36 hours', 'position_created',
     NOW() - INTERVAL '36 hours 3 minutes', 'ABC..VWX'),
    (gen_random_uuid(), wallet5_addr, wif_addr, 'swap_detected', 'buy',
     180, 0.820000, 147.60,
     true, NOW() - INTERVAL '24 hours', 'position_created',
     NOW() - INTERVAL '24 hours 1 minute', 'DEF..YZA'),
    (gen_random_uuid(), wallet4_addr, myro_addr, 'swap_detected', 'buy',
     600, 0.310000, 186.00,
     true, NOW() - INTERVAL '12 hours', 'position_created',
     NOW() - INTERVAL '12 hours 5 minutes', 'GHI..BCD');

    -- Filtered signals (10) - Various rejection reasons
    INSERT INTO walltrack.signals (
        id, wallet_address, token_address, signal_type, action,
        amount, price_usd, value_usd,
        processed, processed_at, action_taken, rejection_reason,
        received_at, helius_signature
    ) VALUES
    -- Signals 11-14: Rejected due to safety score
    (gen_random_uuid(), wallet1_addr, scam_addr, 'swap_detected', 'buy',
     1000000, 0.000050, 50.00,
     true, NOW() - INTERVAL '1 hour', 'rejected_safety', 'safety_score_too_low (0.25 < 0.60)',
     NOW() - INTERVAL '1 hour 2 minutes', 'SCM..EFG'),
    (gen_random_uuid(), wallet3_addr, rug_addr, 'swap_detected', 'buy',
     500000, 0.000080, 40.00,
     true, NOW() - INTERVAL '50 minutes', 'rejected_safety', 'safety_score_too_low (0.18 < 0.60)',
     NOW() - INTERVAL '52 minutes', 'RUG..HIJ'),
    (gen_random_uuid(), wallet2_addr, pump_addr, 'swap_detected', 'buy',
     200000, 0.000200, 40.00,
     true, NOW() - INTERVAL '40 minutes', 'rejected_safety', 'safety_score_too_low (0.42 < 0.60)',
     NOW() - INTERVAL '42 minutes', 'PMP..KLM'),
    (gen_random_uuid(), wallet5_addr, fake_addr, 'swap_detected', 'buy',
     150000, 0.000150, 22.50,
     true, NOW() - INTERVAL '30 minutes', 'rejected_safety', 'safety_score_too_low (0.55 < 0.60)',
     NOW() - INTERVAL '32 minutes', 'FAK..NOP'),

    -- Signals 15-17: Ignored sell signals (we only copy buys)
    (gen_random_uuid(), wallet1_addr, bonk_addr, 'swap_detected', 'sell',
     2000000, 0.0000130, 26.00,
     true, NOW() - INTERVAL '25 minutes', 'ignored_sell', 'sell_signals_not_copied',
     NOW() - INTERVAL '26 minutes', 'SEL..QRS'),
    (gen_random_uuid(), wallet4_addr, wif_addr, 'swap_detected', 'sell',
     100, 0.880000, 88.00,
     true, NOW() - INTERVAL '20 minutes', 'ignored_sell', 'sell_signals_not_copied',
     NOW() - INTERVAL '21 minutes', 'SEL..TUV'),
    (gen_random_uuid(), wallet3_addr, myro_addr, 'swap_detected', 'sell',
     300, 0.335000, 100.50,
     true, NOW() - INTERVAL '15 minutes', 'ignored_sell', 'sell_signals_not_copied',
     NOW() - INTERVAL '16 minutes', 'SEL..WXY'),

    -- Signals 18-20: Circuit breaker active
    (gen_random_uuid(), wallet2_addr, jto_addr, 'swap_detected', 'buy',
     50, 2.200000, 110.00,
     true, NOW() - INTERVAL '10 minutes', 'circuit_breaker_active', 'daily_loss_limit_exceeded',
     NOW() - INTERVAL '11 minutes', 'CBK..ZAB'),
    (gen_random_uuid(), wallet3_addr, bonk_addr, 'swap_detected', 'buy',
     4000000, 0.0000128, 51.20,
     true, NOW() - INTERVAL '8 minutes', 'circuit_breaker_active', 'max_positions_reached',
     NOW() - INTERVAL '9 minutes', 'CBK..CDE'),
    (gen_random_uuid(), wallet1_addr, wif_addr, 'swap_detected', 'buy',
     120, 0.860000, 103.20,
     true, NOW() - INTERVAL '5 minutes', 'circuit_breaker_active', 'wallet_risk_limit',
     NOW() - INTERVAL '6 minutes', 'CBK..FGH');

    RAISE NOTICE '✅ Inserted 20 signals (10 processed, 10 filtered)';
END $$;

-- ============================================================================
-- POSITIONS: 12 positions (6 open, 6 closed)
-- ============================================================================

DO $$
DECLARE
    wallet1_id UUID; wallet2_id UUID; wallet3_id UUID; wallet4_id UUID; wallet5_id UUID;
    bonk_id UUID; wif_id UUID; myro_id UUID; jto_id UUID;
    default_strat_id UUID; conservative_strat_id UUID; aggressive_strat_id UUID;
    sig1_id UUID; sig2_id UUID; sig3_id UUID; sig4_id UUID; sig5_id UUID; sig6_id UUID;
    sig7_id UUID; sig8_id UUID; sig9_id UUID; sig10_id UUID;
BEGIN
    -- Get IDs
    SELECT id INTO wallet1_id FROM walltrack.wallets WHERE address = '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU';
    SELECT id INTO wallet2_id FROM walltrack.wallets WHERE address = 'DYw8jCTfwHNRJhhmFcbXvVDTqWMEVFBX6ZKUmG5CNSKK';
    SELECT id INTO wallet3_id FROM walltrack.wallets WHERE address = 'FwR3PbjS5iyqzLiLugrBqKSa5EKZ4vK2aCPNPdxvNvML';
    SELECT id INTO wallet4_id FROM walltrack.wallets WHERE address = 'BonkMAn3jEyPM3AwAv3xqvZ8ys9Z98MPpDRxQwuXiJ9c';
    SELECT id INTO wallet5_id FROM walltrack.wallets WHERE address = '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM';

    SELECT id INTO bonk_id FROM walltrack.tokens WHERE symbol = 'BONK';
    SELECT id INTO wif_id FROM walltrack.tokens WHERE symbol = 'WIF';
    SELECT id INTO myro_id FROM walltrack.tokens WHERE symbol = 'MYRO';
    SELECT id INTO jto_id FROM walltrack.tokens WHERE symbol = 'JTO';

    SELECT id INTO default_strat_id FROM walltrack.exit_strategies WHERE name = 'Default';
    SELECT id INTO conservative_strat_id FROM walltrack.exit_strategies WHERE name = 'Conservative';
    SELECT id INTO aggressive_strat_id FROM walltrack.exit_strategies WHERE name = 'Aggressive';

    -- Get signal IDs (first 10 processed signals)
    SELECT id INTO sig1_id FROM walltrack.signals WHERE wallet_address = '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU' AND token_address = 'HhJpBhRRn4g56VsyLuT8DL5Bv31HkXqsrahTTUCZeZg4' AND action = 'buy';
    SELECT id INTO sig2_id FROM walltrack.signals WHERE wallet_address = 'DYw8jCTfwHNRJhhmFcbXvVDTqWMEVFBX6ZKUmG5CNSKK' AND token_address = 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263' AND action = 'buy';
    SELECT id INTO sig3_id FROM walltrack.signals WHERE wallet_address = 'FwR3PbjS5iyqzLiLugrBqKSa5EKZ4vK2aCPNPdxvNvML' AND token_address = 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm' AND action = 'buy';
    SELECT id INTO sig4_id FROM walltrack.signals WHERE wallet_address = 'BonkMAn3jEyPM3AwAv3xqvZ8ys9Z98MPpDRxQwuXiJ9c' AND token_address = 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263' AND action = 'buy' AND received_at < NOW() - INTERVAL '5 hours';
    SELECT id INTO sig5_id FROM walltrack.signals WHERE wallet_address = 'BonkMAn3jEyPM3AwAv3xqvZ8ys9Z98MPpDRxQwuXiJ9c' AND token_address = 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm' AND action = 'buy';
    SELECT id INTO sig6_id FROM walltrack.signals WHERE wallet_address = '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM' AND token_address = 'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL' AND action = 'buy';
    SELECT id INTO sig7_id FROM walltrack.signals WHERE wallet_address = '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU' AND token_address = 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263' AND action = 'buy' AND received_at < NOW() - INTERVAL '40 hours';
    SELECT id INTO sig8_id FROM walltrack.signals WHERE wallet_address = 'DYw8jCTfwHNRJhhmFcbXvVDTqWMEVFBX6ZKUmG5CNSKK' AND token_address = 'HhJpBhRRn4g56VsyLuT8DL5Bv31HkXqsrahTTUCZeZg4' AND action = 'buy';
    SELECT id INTO sig9_id FROM walltrack.signals WHERE wallet_address = '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM' AND token_address = 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm' AND action = 'buy' AND received_at < NOW() - INTERVAL '20 hours';
    SELECT id INTO sig10_id FROM walltrack.signals WHERE wallet_address = 'BonkMAn3jEyPM3AwAv3xqvZ8ys9Z98MPpDRxQwuXiJ9c' AND token_address = 'HhJpBhRRn4g56VsyLuT8DL5Bv31HkXqsrahTTUCZeZg4' AND action = 'buy' AND received_at < NOW() - INTERVAL '10 hours';

    -- Open positions (6)
    -- Position 1: Wallet4 (live) BONK - in profit
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        peak_price, peak_value_usd, last_price_update_at,
        unrealized_pnl_usd, unrealized_pnl_percent,
        exit_strategy_id, status
    ) VALUES (
        gen_random_uuid(), wallet4_id, bonk_id, sig4_id, 'live',
        0.0000125, 5000000, 62.50, NOW() - INTERVAL '6 hours', 'ENTRY..001',
        5000000, 0.0000138, 69.00, 6.50, 10.40,
        0.0000142, 71.00, NOW() - INTERVAL '5 minutes',
        6.50, 10.40,
        default_strat_id, 'open'
    );

    -- Position 2: Wallet4 (live) WIF - slight loss
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        peak_price, peak_value_usd, last_price_update_at,
        unrealized_pnl_usd, unrealized_pnl_percent,
        exit_strategy_id, status
    ) VALUES (
        gen_random_uuid(), wallet4_id, wif_id, sig5_id, 'live',
        0.850000, 150, 127.50, NOW() - INTERVAL '5 hours', 'ENTRY..002',
        150, 0.830000, 124.50, -3.00, -2.35,
        0.880000, 132.00, NOW() - INTERVAL '10 minutes',
        -3.00, -2.35,
        default_strat_id, 'open'
    );

    -- Position 3: Wallet5 (live) JTO - in profit
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        peak_price, peak_value_usd, last_price_update_at,
        unrealized_pnl_usd, unrealized_pnl_percent,
        exit_strategy_id, status
    ) VALUES (
        gen_random_uuid(), wallet5_id, jto_id, sig6_id, 'live',
        2.150000, 80, 172.00, NOW() - INTERVAL '4 hours', 'ENTRY..003',
        80, 2.420000, 193.60, 21.60, 12.56,
        2.500000, 200.00, NOW() - INTERVAL '15 minutes',
        21.60, 12.56,
        aggressive_strat_id, 'open'
    );

    -- Position 4: Wallet1 (simulation) MYRO - in profit
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        peak_price, peak_value_usd, last_price_update_at,
        unrealized_pnl_usd, unrealized_pnl_percent,
        exit_strategy_id, status
    ) VALUES (
        gen_random_uuid(), wallet1_id, myro_id, sig1_id, 'simulation',
        0.320000, 400, 128.00, NOW() - INTERVAL '3 hours', NULL,
        400, 0.345000, 138.00, 10.00, 7.81,
        0.355000, 142.00, NOW() - INTERVAL '8 minutes',
        10.00, 7.81,
        default_strat_id, 'open'
    );

    -- Position 5: Wallet2 (simulation) BONK - breakeven
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        peak_price, peak_value_usd, last_price_update_at,
        unrealized_pnl_usd, unrealized_pnl_percent,
        exit_strategy_id, status
    ) VALUES (
        gen_random_uuid(), wallet2_id, bonk_id, sig2_id, 'simulation',
        0.0000120, 8000000, 96.00, NOW() - INTERVAL '2 hours 30 minutes', NULL,
        8000000, 0.0000121, 96.80, 0.80, 0.83,
        0.0000128, 102.40, NOW() - INTERVAL '12 minutes',
        0.80, 0.83,
        conservative_strat_id, 'open'
    );

    -- Position 6: Wallet3 (simulation) WIF - small profit
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        peak_price, peak_value_usd, last_price_update_at,
        unrealized_pnl_usd, unrealized_pnl_percent,
        exit_strategy_id, status
    ) VALUES (
        gen_random_uuid(), wallet3_id, wif_id, sig3_id, 'simulation',
        0.830000, 200, 166.00, NOW() - INTERVAL '2 hours', NULL,
        200, 0.855000, 171.00, 5.00, 3.01,
        0.880000, 176.00, NOW() - INTERVAL '6 minutes',
        5.00, 3.01,
        aggressive_strat_id, 'open'
    );

    -- Closed positions (6)
    -- Position 7: Wallet1 BONK - closed at profit (stop loss)
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        peak_price, peak_value_usd, last_price_update_at,
        realized_pnl_usd, realized_pnl_percent,
        exit_price, exit_amount, exit_value_usd, exit_timestamp, exit_tx_signature, exit_reason,
        exit_strategy_id, status, closed_at
    ) VALUES (
        gen_random_uuid(), wallet1_id, bonk_id, sig7_id, 'simulation',
        0.0000118, 3000000, 35.40, NOW() - INTERVAL '48 hours', NULL,
        0, 0.0000130, 0, 3.60, 10.17,
        0.0000135, 40.50, NOW() - INTERVAL '24 hours',
        3.60, 10.17,
        0.0000130, 3000000, 39.00, NOW() - INTERVAL '24 hours', NULL, 'trailing_stop',
        default_strat_id, 'closed', NOW() - INTERVAL '24 hours'
    );

    -- Position 8: Wallet2 MYRO - closed at loss (stop loss triggered)
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        realized_pnl_usd, realized_pnl_percent,
        exit_price, exit_amount, exit_value_usd, exit_timestamp, exit_tx_signature, exit_reason,
        exit_strategy_id, status, closed_at
    ) VALUES (
        gen_random_uuid(), wallet2_id, myro_id, sig8_id, 'simulation',
        0.295000, 500, 147.50, NOW() - INTERVAL '36 hours', NULL,
        0, 0.250000, 0, -22.50, -15.25,
        -22.50, -15.25,
        0.250000, 500, 125.00, NOW() - INTERVAL '30 hours', NULL, 'stop_loss',
        conservative_strat_id, 'closed', NOW() - INTERVAL '30 hours'
    );

    -- Position 9: Wallet5 WIF - closed at profit (manual exit)
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        realized_pnl_usd, realized_pnl_percent,
        exit_price, exit_amount, exit_value_usd, exit_timestamp, exit_tx_signature, exit_reason,
        exit_strategy_id, status, closed_at
    ) VALUES (
        gen_random_uuid(), wallet5_id, wif_id, sig9_id, 'live',
        0.820000, 180, 147.60, NOW() - INTERVAL '24 hours', 'ENTRY..009',
        0, 0.920000, 0, 18.00, 12.20,
        18.00, 12.20,
        0.920000, 180, 165.60, NOW() - INTERVAL '12 hours', 'EXIT..009', 'manual',
        aggressive_strat_id, 'closed', NOW() - INTERVAL '12 hours'
    );

    -- Position 10: Wallet4 MYRO - closed at profit (scaling out complete)
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature,
        current_amount, current_price, current_value_usd, current_pnl_usd, current_pnl_percent,
        realized_pnl_usd, realized_pnl_percent,
        exit_price, exit_amount, exit_value_usd, exit_timestamp, exit_tx_signature, exit_reason,
        exit_strategy_id, status, closed_at
    ) VALUES (
        gen_random_uuid(), wallet4_id, myro_id, sig10_id, 'live',
        0.310000, 600, 186.00, NOW() - INTERVAL '12 hours', 'ENTRY..010',
        0, 0.350000, 0, 24.00, 12.90,
        24.00, 12.90,
        0.350000, 600, 210.00, NOW() - INTERVAL '6 hours', 'EXIT..010', 'scaling_out',
        default_strat_id, 'closed', NOW() - INTERVAL '6 hours'
    );

    -- Positions 11-12: Simulation closed positions
    INSERT INTO walltrack.positions (
        id, wallet_id, token_id, signal_id, mode,
        entry_price, entry_amount, entry_value_usd, entry_timestamp,
        current_amount, realized_pnl_usd, realized_pnl_percent,
        exit_price, exit_amount, exit_value_usd, exit_timestamp, exit_reason,
        exit_strategy_id, status, closed_at
    ) VALUES
    (gen_random_uuid(), wallet3_id, myro_id, sig1_id, 'simulation',
     0.305000, 350, 106.75, NOW() - INTERVAL '20 hours',
     0, 8.75, 8.20,
     0.330000, 350, 115.50, NOW() - INTERVAL '15 hours', 'mirror_exit',
     aggressive_strat_id, 'closed', NOW() - INTERVAL '15 hours'),
    (gen_random_uuid(), wallet1_id, wif_id, sig5_id, 'simulation',
     0.840000, 120, 100.80, NOW() - INTERVAL '18 hours',
     0, -5.04, -5.00,
     0.798000, 120, 95.76, NOW() - INTERVAL '10 hours', 'stop_loss',
     default_strat_id, 'closed', NOW() - INTERVAL '10 hours');

    RAISE NOTICE '✅ Inserted 12 positions (6 open, 6 closed)';
END $$;

-- ============================================================================
-- ORDERS: 18 orders (12 filled, 4 pending, 2 failed)
-- ============================================================================

DO $$
DECLARE
    wallet1_id UUID; wallet2_id UUID; wallet3_id UUID; wallet4_id UUID; wallet5_id UUID;
    bonk_id UUID; wif_id UUID; myro_id UUID; jto_id UUID;
    pos1_id UUID; pos2_id UUID; pos3_id UUID; pos4_id UUID;
    sig4_id UUID; sig5_id UUID; sig6_id UUID;
BEGIN
    -- Get IDs
    SELECT id INTO wallet1_id FROM walltrack.wallets WHERE address = '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU';
    SELECT id INTO wallet2_id FROM walltrack.wallets WHERE address = 'DYw8jCTfwHNRJhhmFcbXvVDTqWMEVFBX6ZKUmG5CNSKK';
    SELECT id INTO wallet3_id FROM walltrack.wallets WHERE address = 'FwR3PbjS5iyqzLiLugrBqKSa5EKZ4vK2aCPNPdxvNvML';
    SELECT id INTO wallet4_id FROM walltrack.wallets WHERE address = 'BonkMAn3jEyPM3AwAv3xqvZ8ys9Z98MPpDRxQwuXiJ9c';
    SELECT id INTO wallet5_id FROM walltrack.wallets WHERE address = '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM';

    SELECT id INTO bonk_id FROM walltrack.tokens WHERE symbol = 'BONK';
    SELECT id INTO wif_id FROM walltrack.tokens WHERE symbol = 'WIF';
    SELECT id INTO myro_id FROM walltrack.tokens WHERE symbol = 'MYRO';
    SELECT id INTO jto_id FROM walltrack.tokens WHERE symbol = 'JTO';

    SELECT id INTO sig4_id FROM walltrack.signals WHERE wallet_address = 'BonkMAn3jEyPM3AwAv3xqvZ8ys9Z98MPpDRxQwuXiJ9c' AND token_address = 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263' AND action = 'buy' AND received_at < NOW() - INTERVAL '5 hours';
    SELECT id INTO sig5_id FROM walltrack.signals WHERE wallet_address = 'BonkMAn3jEyPM3AwAv3xqvZ8ys9Z98MPpDRxQwuXiJ9c' AND token_address = 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm' AND action = 'buy';
    SELECT id INTO sig6_id FROM walltrack.signals WHERE wallet_address = '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM' AND token_address = 'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL' AND action = 'buy';

    -- Get first 4 open position IDs
    SELECT id INTO pos1_id FROM walltrack.positions WHERE wallet_id = wallet4_id AND token_id = bonk_id AND status = 'open';
    SELECT id INTO pos2_id FROM walltrack.positions WHERE wallet_id = wallet4_id AND token_id = wif_id AND status = 'open';
    SELECT id INTO pos3_id FROM walltrack.positions WHERE wallet_id = wallet5_id AND token_id = jto_id AND status = 'open';
    SELECT id INTO pos4_id FROM walltrack.positions WHERE wallet_id = wallet1_id AND token_id = myro_id AND status = 'open';

    -- Executed orders (12) - Entry and exit orders that filled
    -- Orders 1-6: Entry orders (filled)
    INSERT INTO walltrack.orders (
        id, wallet_id, token_id, position_id, signal_id, mode, order_type,
        requested_price, requested_amount, requested_value_usd, requested_at,
        executed_price, executed_amount, executed_value_usd, executed_at,
        tx_signature, slippage_percent, status, execution_duration_ms
    ) VALUES
    (gen_random_uuid(), wallet4_id, bonk_id, pos1_id, sig4_id, 'live', 'entry',
     0.0000125, 5000000, 62.50, NOW() - INTERVAL '6 hours',
     0.0000126, 5000000, 63.00, NOW() - INTERVAL '5 hours 59 minutes',
     'TXSIG..001', 0.80, 'executed', 1250),
    (gen_random_uuid(), wallet4_id, wif_id, pos2_id, sig5_id, 'live', 'entry',
     0.850000, 150, 127.50, NOW() - INTERVAL '5 hours',
     0.852000, 150, 127.80, NOW() - INTERVAL '4 hours 59 minutes',
     'TXSIG..002', 0.24, 'executed', 980),
    (gen_random_uuid(), wallet5_id, jto_id, pos3_id, sig6_id, 'live', 'entry',
     2.150000, 80, 172.00, NOW() - INTERVAL '4 hours',
     2.155000, 80, 172.40, NOW() - INTERVAL '3 hours 59 minutes',
     'TXSIG..003', 0.23, 'executed', 1100),
    (gen_random_uuid(), wallet1_id, myro_id, pos4_id, NULL, 'simulation', 'entry',
     0.320000, 400, 128.00, NOW() - INTERVAL '3 hours',
     0.320000, 400, 128.00, NOW() - INTERVAL '2 hours 59 minutes',
     NULL, 0.00, 'executed', 50),
    (gen_random_uuid(), wallet2_id, bonk_id, NULL, NULL, 'simulation', 'entry',
     0.0000120, 8000000, 96.00, NOW() - INTERVAL '2 hours 30 minutes',
     0.0000120, 8000000, 96.00, NOW() - INTERVAL '2 hours 29 minutes',
     NULL, 0.00, 'executed', 45),
    (gen_random_uuid(), wallet3_id, wif_id, NULL, NULL, 'simulation', 'entry',
     0.830000, 200, 166.00, NOW() - INTERVAL '2 hours',
     0.830000, 200, 166.00, NOW() - INTERVAL '1 hour 59 minutes',
     NULL, 0.00, 'executed', 52);

    -- Orders 7-12: Exit orders (filled)
    INSERT INTO walltrack.orders (
        id, wallet_id, token_id, position_id, mode, order_type,
        requested_price, requested_amount, requested_value_usd, requested_at,
        executed_price, executed_amount, executed_value_usd, executed_at,
        tx_signature, slippage_percent, status, execution_duration_ms
    ) VALUES
    (gen_random_uuid(), wallet1_id, bonk_id, NULL, 'simulation', 'exit_trailing_stop',
     0.0000130, 3000000, 39.00, NOW() - INTERVAL '24 hours',
     0.0000130, 3000000, 39.00, NOW() - INTERVAL '23 hours 59 minutes',
     NULL, 0.00, 'executed', 60),
    (gen_random_uuid(), wallet2_id, myro_id, NULL, 'simulation', 'exit_stop_loss',
     0.250000, 500, 125.00, NOW() - INTERVAL '30 hours',
     0.248000, 500, 124.00, NOW() - INTERVAL '29 hours 59 minutes',
     NULL, -0.80, 'executed', 75),
    (gen_random_uuid(), wallet5_id, wif_id, NULL, 'live', 'exit_manual',
     0.920000, 180, 165.60, NOW() - INTERVAL '12 hours',
     0.918000, 180, 165.24, NOW() - INTERVAL '11 hours 59 minutes',
     'TXSIG..008', -0.22, 'executed', 1450),
    (gen_random_uuid(), wallet4_id, myro_id, NULL, 'live', 'exit_scaling',
     0.350000, 300, 105.00, NOW() - INTERVAL '8 hours',
     0.352000, 300, 105.60, NOW() - INTERVAL '7 hours 59 minutes',
     'TXSIG..009', 0.57, 'executed', 1320),
    (gen_random_uuid(), wallet4_id, myro_id, NULL, 'live', 'exit_scaling',
     0.350000, 300, 105.00, NOW() - INTERVAL '6 hours',
     0.349000, 300, 104.70, NOW() - INTERVAL '5 hours 59 minutes',
     'TXSIG..010', -0.29, 'executed', 1180),
    (gen_random_uuid(), wallet3_id, myro_id, NULL, 'simulation', 'exit_mirror',
     0.330000, 350, 115.50, NOW() - INTERVAL '15 hours',
     0.330000, 350, 115.50, NOW() - INTERVAL '14 hours 59 minutes',
     NULL, 0.00, 'executed', 55);

    -- Pending orders (4)
    INSERT INTO walltrack.orders (
        id, wallet_id, token_id, position_id, mode, order_type,
        requested_price, requested_amount, requested_value_usd, requested_at,
        status
    ) VALUES
    (gen_random_uuid(), wallet4_id, bonk_id, pos1_id, 'live', 'exit_trailing_stop',
     0.0000140, 5000000, 70.00, NOW() - INTERVAL '30 minutes',
     'pending'),
    (gen_random_uuid(), wallet5_id, jto_id, pos3_id, 'live', 'exit_trailing_stop',
     2.500000, 80, 200.00, NOW() - INTERVAL '25 minutes',
     'pending'),
    (gen_random_uuid(), wallet1_id, myro_id, pos4_id, 'simulation', 'exit_scaling',
     0.355000, 200, 71.00, NOW() - INTERVAL '20 minutes',
     'pending'),
    (gen_random_uuid(), wallet2_id, bonk_id, NULL, 'simulation', 'exit_stop_loss',
     0.0000105, 8000000, 84.00, NOW() - INTERVAL '15 minutes',
     'pending');

    -- Failed orders (2) - with retry
    INSERT INTO walltrack.orders (
        id, wallet_id, token_id, position_id, mode, order_type,
        requested_price, requested_amount, requested_value_usd, requested_at,
        retry_count, max_retries, retry_reason, status
    ) VALUES
    (gen_random_uuid(), wallet4_id, wif_id, pos2_id, 'live', 'exit_stop_loss',
     0.800000, 150, 120.00, NOW() - INTERVAL '45 minutes',
     2, 3, 'insufficient_liquidity', 'failed'),
    (gen_random_uuid(), wallet3_id, wif_id, NULL, 'simulation', 'entry',
     0.860000, 250, 215.00, NOW() - INTERVAL '1 hour',
     1, 3, 'rpc_timeout', 'failed');

    RAISE NOTICE '✅ Inserted 18 orders (12 executed, 4 pending, 2 failed)';
END $$;

-- Rollback
-- DELETE FROM walltrack.orders;
-- DELETE FROM walltrack.positions;
-- DELETE FROM walltrack.signals;
