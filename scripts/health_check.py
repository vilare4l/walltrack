#!/usr/bin/env python3
"""
WallTrack Health Check Script (Python version)

Checks that all required services are healthy and responding.
This version works on all platforms (Windows, Linux, macOS).

Usage:
    python scripts/health_check.py
    uv run python scripts/health_check.py

Exit codes:
    0 - All services healthy
    1 - One or more services unhealthy
"""

from __future__ import annotations

import os
import sys
from typing import TypedDict

# Fix Windows encoding issue
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import httpx
from neo4j import GraphDatabase


class HealthStatus(TypedDict):
    """Health check result for a single service."""

    name: str
    healthy: bool
    message: str


# Colors for terminal output
class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    NC = "\033[0m"  # No Color


def check_fastapi_health(api_url: str) -> dict[str, HealthStatus]:
    """
    Check FastAPI health endpoint and all dependent services.

    This endpoint checks the health of all services (FastAPI, Neo4j, Supabase)
    in one call, which is more reliable than trying to connect directly.

    Args:
        api_url: Base URL of the FastAPI server (e.g., http://localhost:8080)

    Returns:
        Dict of service names to HealthStatus results
    """
    results: dict[str, HealthStatus] = {}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{api_url}/api/health")
            response.raise_for_status()

            data = response.json()
            overall_status = data.get("status", "unknown")

            # Check overall FastAPI status
            results["FastAPI"] = {
                "name": "FastAPI",
                "healthy": overall_status in ("ok", "degraded"),
                "message": f"Status: {overall_status}",
            }

            # Check database statuses from health response
            databases = data.get("databases", {})

            if "supabase" in databases:
                supabase_healthy = databases["supabase"].get("healthy", False)
                supabase_status = databases["supabase"].get("status", "unknown")
                results["Supabase"] = {
                    "name": "Supabase",
                    "healthy": supabase_healthy,
                    "message": f"Status: {supabase_status}",
                }

            if "neo4j" in databases:
                neo4j_healthy = databases["neo4j"].get("healthy", False)
                neo4j_status = databases["neo4j"].get("status", "unknown")
                results["Neo4j"] = {
                    "name": "Neo4j",
                    "healthy": neo4j_healthy,
                    "message": f"Status: {neo4j_status}",
                }

            return results

    except httpx.HTTPError as e:
        results["FastAPI"] = {
            "name": "FastAPI",
            "healthy": False,
            "message": f"HTTP error: {e}",
        }
        return results

    except Exception as e:
        results["FastAPI"] = {
            "name": "FastAPI",
            "healthy": False,
            "message": f"Error: {e}",
        }
        return results


def check_neo4j_connection(uri: str, user: str, password: str) -> HealthStatus:
    """
    Check Neo4j connection.

    Args:
        uri: Neo4j URI (e.g., bolt://localhost:7687)
        user: Neo4j username
        password: Neo4j password

    Returns:
        HealthStatus with result
    """
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))

        # Verify connection with simple query
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) LIMIT 1")
            count = result.single()[0]

        driver.close()

        return {
            "name": "Neo4j",
            "healthy": True,
            "message": f"Connected (nodes: {count})",
        }

    except Exception as e:
        return {
            "name": "Neo4j",
            "healthy": False,
            "message": f"Connection failed: {e}",
        }


def check_supabase_connection(database_url: str) -> HealthStatus:
    """
    Check Supabase/PostgreSQL connection.

    Args:
        database_url: PostgreSQL connection string

    Returns:
        HealthStatus with result
    """
    try:
        import psycopg2

        # Parse connection URL (postgresql://user:pass@host:port/db)
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()

        return {
            "name": "Supabase/PostgreSQL",
            "healthy": True,
            "message": "Connected",
        }

    except ImportError:
        return {
            "name": "Supabase/PostgreSQL",
            "healthy": False,
            "message": "psycopg2 not installed (pip install psycopg2-binary)",
        }
    except Exception as e:
        return {
            "name": "Supabase/PostgreSQL",
            "healthy": False,
            "message": f"Connection failed: {e}",
        }


def main() -> int:
    """
    Run health checks for all services.

    Returns:
        Exit code (0 if all healthy, 1 if any unhealthy)
    """
    # Load configuration from environment
    # Note: Default to port 8080 (Docker mapped port) instead of 8000 (internal)
    api_url = os.getenv("API_URL", "http://localhost:8080")

    print("=" * 50)
    print("WallTrack Health Check")
    print("=" * 50)
    print()

    # Run health checks via API endpoint
    # This checks FastAPI + all dependent services (Neo4j, Supabase)
    print("Checking services via /api/health endpoint...")
    health_results = check_fastapi_health(api_url)

    # Print results
    print()
    print("=" * 50)
    print("Results:")
    print("=" * 50)

    all_healthy = True
    for result in health_results.values():
        if result["healthy"]:
            status = f"{Colors.GREEN}✓ OK{Colors.NC}"
        else:
            status = f"{Colors.RED}✗ FAILED{Colors.NC}"
            all_healthy = False

        print(f"{result['name']:<25} {status}")
        print(f"  {result['message']}")

    print()
    print("=" * 50)

    if all_healthy:
        print(f"{Colors.GREEN}✓ All services are healthy{Colors.NC}")
        print("=" * 50)
        return 0
    else:
        print(f"{Colors.RED}✗ Some services are unhealthy{Colors.NC}")
        print("=" * 50)
        print()
        print("Troubleshooting:")
        print("  1. Ensure docker-compose is running: docker compose ps")
        print("  2. Check logs: docker compose logs")
        print("  3. Verify .env file has correct credentials")
        print(f"  4. Check API health directly: curl {api_url}/api/health")
        return 1


if __name__ == "__main__":
    sys.exit(main())
