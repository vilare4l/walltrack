#!/usr/bin/env bash
# =============================================================================
# WallTrack Health Check Script
# =============================================================================
#
# Checks that all required services are healthy and responding.
#
# Usage:
#   ./scripts/health-check.sh
#
# Exit codes:
#   0 - All services healthy
#   1 - One or more services unhealthy
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-walltrackpass}"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/postgres}"

# Health status tracking
ALL_HEALTHY=true

echo "========================================="
echo "WallTrack Health Check"
echo "========================================="
echo ""

# =========================================================================
# 1. Check FastAPI Health Endpoint
# =========================================================================
echo -n "Checking FastAPI health endpoint... "

if curl -f -s "${API_URL}/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
    echo "  FastAPI health endpoint not responding at ${API_URL}/api/health"
    ALL_HEALTHY=false
fi

# =========================================================================
# 2. Check Supabase / PostgreSQL
# =========================================================================
echo -n "Checking PostgreSQL/Supabase connection... "

# Extract connection params from DATABASE_URL
# Format: postgresql://user:pass@host:port/db
if command -v psql > /dev/null 2>&1; then
    if psql "${DATABASE_URL}" -c "SELECT 1" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Cannot connect to PostgreSQL at ${DATABASE_URL}"
        ALL_HEALTHY=false
    fi
else
    echo -e "${YELLOW}⚠ SKIPPED${NC}"
    echo "  psql not installed - cannot verify PostgreSQL connection"
    echo "  Install postgresql-client: sudo apt install postgresql-client"
fi

# =========================================================================
# 3. Check Neo4j
# =========================================================================
echo -n "Checking Neo4j connection... "

# Use cypher-shell if available
if command -v cypher-shell > /dev/null 2>&1; then
    if cypher-shell -a "${NEO4J_URI}" -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" \
        "MATCH (n) RETURN count(n) LIMIT 1" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Cannot connect to Neo4j at ${NEO4J_URI}"
        ALL_HEALTHY=false
    fi
else
    # Fallback: Use HTTP API (port 7474)
    NEO4J_HTTP="${NEO4J_URI/bolt/http}"
    NEO4J_HTTP="${NEO4J_HTTP/:7687/:7474}"

    if curl -f -s -u "${NEO4J_USER}:${NEO4J_PASSWORD}" "${NEO4J_HTTP}/db/neo4j/tx/commit" \
        -H "Content-Type: application/json" \
        -d '{"statements":[{"statement":"MATCH (n) RETURN count(n) LIMIT 1"}]}' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${YELLOW}⚠ SKIPPED${NC}"
        echo "  cypher-shell not installed and HTTP API check failed"
        echo "  Install cypher-shell: https://neo4j.com/docs/operations-manual/current/tools/cypher-shell/"
    fi
fi

# =========================================================================
# Summary
# =========================================================================
echo ""
echo "========================================="

if [ "$ALL_HEALTHY" = true ]; then
    echo -e "${GREEN}✓ All services are healthy${NC}"
    echo "========================================="
    exit 0
else
    echo -e "${RED}✗ Some services are unhealthy${NC}"
    echo "========================================="
    echo ""
    echo "Troubleshooting:"
    echo "  1. Ensure docker-compose is running: docker compose ps"
    echo "  2. Check logs: docker compose logs"
    echo "  3. Verify .env file has correct credentials"
    exit 1
fi
