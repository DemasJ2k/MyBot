"""
End-to-End Test Suite for Flowrex Trading Platform.

These tests verify complete user workflows across the entire stack:
- Frontend → Backend API → Database → External Services

Prerequisites:
- Running backend server (localhost:8000)
- Running frontend server (localhost:3000)
- PostgreSQL and Redis running
- Test environment configured

Run with: pytest tests/e2e/ -v --e2e
"""
import pytest

# Mark all tests in this directory as e2e
pytestmark = pytest.mark.e2e
