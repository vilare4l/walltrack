# Supabase Migrations

## Overview

This folder contains SQL migrations for the WallTrack V2 Supabase database.

## Migration Naming Convention

```
NNN_description.sql
```

- `NNN`: 3-digit sequence number (001, 002, etc.)
- `description`: brief snake_case description

## Current Migrations

| Migration | Description | Tables |
|-----------|-------------|--------|
| 001_config.sql | Key-value config storage | `config` |

## How to Apply Migrations

### Option 1: Supabase Dashboard (Recommended)

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Copy/paste the migration content
4. Click **Run**

### Option 2: Via psql

```bash
# Get DATABASE_URL from Supabase project settings
psql $DATABASE_URL -f src/walltrack/data/supabase/migrations/001_config.sql
```

### Option 3: Via Supabase CLI

```bash
# If using supabase CLI with local development
supabase db push
```

## Migration Order

Migrations must be applied in sequence. Each migration is idempotent (can be run multiple times safely due to `IF NOT EXISTS` clauses).

## Notes

- V2 uses the default `public` schema (no `walltrack.` prefix like V1)
- All tables include `updated_at` triggers
- RLS is enabled with service_role access policies
