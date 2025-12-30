# Code Review Attack Plan - Story 3.1
## Adversarial Review Strategy

**Story Type:** Feature (Wallet Discovery)
**Risk Profile:** HIGH - Multi-database, async orchestration, dual-sync architecture

---

## Attack Vectors (Prioritized)

### 1. Documentation Integrity (CRITICAL - Step 1 findings)
**Finding:** File List incomplete - 9 fichiers non documentés (56% du scope manquant)

**Attack:**
- Cross-reference tous les fichiers modifiés avec tasks
- Valider si extensions de scope étaient nécessaires
- Vérifier si AC peuvent être satisfaits avec fichiers documentés seuls
- Identifier scope creep vs necessary dependencies

**Files to Audit:**
- `src/walltrack/data/models/token.py` (MODIFIED - pourquoi?)
- `src/walltrack/data/supabase/repositories/token_repo.py` (MODIFIED - pourquoi?)
- `src/walltrack/services/solana/rpc_client.py` (MODIFIED - pourquoi?)
- `src/walltrack/services/solana/models.py` (NEW - pourquoi?)
- `src/walltrack/data/supabase/migrations/002b_tokens_add_wallets_discovered.sql` (CRITICAL - pourquoi absent?)
- `src/walltrack/data/supabase/migrations/003_wallets_table.sql` (CRITICAL - pourquoi absent?)

### 2. Acceptance Criteria Compliance
**ACs to validate:**
- AC1: Discover wallets from token holders → verify orchestration logic
- AC2: Dual-sync Supabase+Neo4j → verify both DBs get data
- AC3: UI Wallets tab functional → verify Explorer page implementation
- AC4: Config trigger works → verify Config page button

**Attack:**
- Run acceptance tests if exist
- Manual validation via UI screenshots/traces
- Check for edge cases: empty tokens, RPC failures, Neo4j down, duplicates

### 3. Task Completion Verification
**8 Tasks × 32 Subtasks = all marked [x] in story**

**Attack:**
- Task 1 (Solana RPC): Verify `rpc_client.py` modifications match subtasks
- Task 2 (Tokens table): Check if migration 002b matches schema requirements
- Task 3 (Wallets table): Check if migration 003 + repository match schema
- Task 4 (Neo4j): Verify MERGE query idempotency
- Task 5 (Orchestration): Verify `run_wallet_discovery()` logic matches AC1
- Task 6 (UI Explorer): Verify Wallets accordion implementation
- Task 7 (UI Config): Verify trigger button + handler
- Task 8 (Integration): Check test coverage (27 tests claim)

### 4. Code Quality Deep Dive
**Focus areas:**
- Error handling in async orchestration (continue on error? partial failures?)
- Race conditions in dual-DB sync (what if Neo4j fails after Supabase insert?)
- Repository pattern consistency (DI usage, mocking in tests)
- Test coverage gaps (edge cases, error paths)
- CLAUDE.md compliance (migrations required, legacy consultation)

### 5. Technical Debt & Anti-patterns
**Look for:**
- Hardcoded values (KNOWN_PROGRAM_ADDRESSES - extensible?)
- Magic numbers (limit=50, limit=100 - configurable?)
- TODO comments left in code
- Missing docstrings
- Type hints incomplete

---

## Review Execution Order

1. **File List Audit** (highest priority - documentation gap)
2. **Migration Files Review** (critical - DB schema foundation)
3. **Orchestration Logic** (complex async flow - error-prone)
4. **Dual-Sync Validation** (architectural risk - data consistency)
5. **UI Implementation** (user-facing - UX issues)
6. **Test Coverage Analysis** (quality assurance)
7. **Code Quality Scan** (technical debt)

---

## Expected Issue Count Target

**Minimum:** 3-10 issues (workflow mandate)
**Predicted:** 8-12 issues based on:
- Documentation gaps (2-3 issues)
- Migration schema issues (1-2 issues)
- Error handling gaps (2-3 issues)
- Code quality (2-3 issues)
- Test coverage gaps (1-2 issues)

---

## Success Criteria for Review

- All file changes explained and justified
- All ACs validated with evidence
- All tasks cross-checked with implementation
- Minimum 3 actionable issues found
- Fix plan proposed for each issue
