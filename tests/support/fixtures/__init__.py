"""
Test Fixtures Package

This package contains reusable test fixtures organized by domain:
- auth_fixtures.py: Authentication and session management
- db_fixtures.py: Database setup and teardown
- api_fixtures.py: API request helpers

Usage:
    Import fixtures in conftest.py or directly in test files.

Pattern:
    1. Pure functions for logic (testable without Playwright)
    2. Fixtures for dependency injection
    3. Composition via pytest fixture dependencies
"""
