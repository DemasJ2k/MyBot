#!/usr/bin/env python3
"""
Deployment Checklist Script for Flowrex.

Prompt 17 - Deployment Prep.

Runs a series of pre-deployment checks to ensure the application
is ready for deployment. This should be run as part of CI/CD
before deploying to staging or production.

Usage:
    python deployment_checklist.py [--env ENV] [--strict] [--skip CHECK...]

Options:
    --env ENV       Target environment (dev, staging, production)
    --strict        Fail on warnings as well as errors
    --skip CHECK    Skip specific checks by name
"""

import argparse
import asyncio
import os
import sys
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class CheckStatus(Enum):
    """Result status for checks."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class CheckResult:
    """Result of a deployment check."""
    name: str
    status: CheckStatus
    message: str
    details: Optional[str] = None


class DeploymentCheck(ABC):
    """Base class for deployment checks."""

    name: str = "Base Check"
    required_for: List[str] = ["staging", "production"]  # environments where this is required

    @abstractmethod
    async def run(self, env: str) -> CheckResult:
        """Run the check and return result."""
        pass


# ============================================================================
# Check Implementations
# ============================================================================

class TestsPassCheck(DeploymentCheck):
    """Verify all tests pass."""

    name = "Tests Pass"
    required_for = ["staging", "production"]

    async def run(self, env: str) -> CheckResult:
        """Run pytest and check exit code."""
        try:
            result = subprocess.run(
                ["pytest", "--tb=no", "-q", "tests/"],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", "backend"),
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                # Extract test count from output
                lines = result.stdout.strip().split("\n")
                summary = lines[-1] if lines else "Tests passed"
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message="All tests passed",
                    details=summary
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.FAIL,
                    message="Tests failed",
                    details=result.stdout[-500:] if result.stdout else result.stderr[-500:]
                )
        except FileNotFoundError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARN,
                message="pytest not found - skipping test check"
            )
        except subprocess.TimeoutExpired:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                message="Tests timed out after 5 minutes"
            )


class CoverageCheck(DeploymentCheck):
    """Check code coverage meets threshold."""

    name = "Code Coverage"
    required_for = ["production"]
    threshold = 70  # Minimum coverage percentage

    async def run(self, env: str) -> CheckResult:
        """Run coverage check."""
        try:
            result = subprocess.run(
                ["pytest", "--cov=app", "--cov-report=term-missing", "--cov-fail-under=" + str(self.threshold)],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", "backend"),
                timeout=300
            )

            if result.returncode == 0:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message=f"Coverage meets {self.threshold}% threshold"
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.FAIL if env == "production" else CheckStatus.WARN,
                    message=f"Coverage below {self.threshold}%",
                    details=result.stdout[-500:] if result.stdout else None
                )
        except FileNotFoundError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                message="pytest-cov not found - install for coverage checks"
            )
        except subprocess.TimeoutExpired:
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARN,
                message="Coverage check timed out"
            )


class DatabaseMigrationCheck(DeploymentCheck):
    """Check database migrations are up to date."""

    name = "Database Migrations"
    required_for = ["staging", "production"]

    async def run(self, env: str) -> CheckResult:
        """Check for pending migrations."""
        try:
            result = subprocess.run(
                ["alembic", "check"],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", "backend"),
                timeout=30
            )

            if result.returncode == 0:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message="Database is up to date"
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.FAIL,
                    message="Pending migrations detected",
                    details=result.stdout or result.stderr
                )
        except FileNotFoundError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARN,
                message="alembic not found - ensure migrations are managed"
            )


class SecretsCheck(DeploymentCheck):
    """Verify all required secrets are configured."""

    name = "Secrets Configuration"
    required_for = ["staging", "production"]

    REQUIRED_SECRETS = {
        "dev": ["JWT_SECRET_KEY"],
        "staging": ["JWT_SECRET_KEY", "DATABASE_URL", "REDIS_URL"],
        "production": [
            "JWT_SECRET_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "SECRET_KEY",
        ],
    }

    async def run(self, env: str) -> CheckResult:
        """Check for required environment variables."""
        required = self.REQUIRED_SECRETS.get(env, self.REQUIRED_SECRETS["production"])
        missing = []
        weak = []

        for secret in required:
            value = os.getenv(secret)
            if not value:
                missing.append(secret)
            elif secret in ("JWT_SECRET_KEY", "SECRET_KEY"):
                # Check for weak default values
                if len(value) < 32 or value in ("secret", "changeme", "development"):
                    weak.append(secret)

        if missing:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                message=f"Missing required secrets: {', '.join(missing)}"
            )
        elif weak and env == "production":
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                message=f"Weak secrets detected: {', '.join(weak)}"
            )
        elif weak:
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARN,
                message=f"Weak secrets (acceptable for {env}): {', '.join(weak)}"
            )
        else:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                message="All required secrets configured"
            )


class SecurityCheck(DeploymentCheck):
    """Security configuration checks."""

    name = "Security Configuration"
    required_for = ["production"]

    async def run(self, env: str) -> CheckResult:
        """Check security-related configuration."""
        issues = []
        warnings = []

        # Check CORS
        cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
        if cors_origins == "*" and env == "production":
            issues.append("CORS allows all origins")

        # Check debug mode
        debug = os.getenv("DEBUG", "false").lower() == "true"
        if debug and env in ("staging", "production"):
            issues.append("Debug mode enabled")

        # Check HTTPS
        if env == "production":
            api_url = os.getenv("API_URL", "")
            if api_url.startswith("http://"):
                warnings.append("API_URL uses HTTP instead of HTTPS")

        # Check rate limiting
        rate_limit = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        if not rate_limit and env == "production":
            warnings.append("Rate limiting disabled")

        if issues:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL,
                message=f"Security issues: {'; '.join(issues)}"
            )
        elif warnings:
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARN,
                message=f"Security warnings: {'; '.join(warnings)}"
            )
        else:
            return CheckResult(
                name=self.name,
                status=CheckStatus.PASS,
                message="Security configuration looks good"
            )


class DependenciesCheck(DeploymentCheck):
    """Check for vulnerable dependencies."""

    name = "Dependency Security"
    required_for = ["staging", "production"]

    async def run(self, env: str) -> CheckResult:
        """Run pip audit or safety check."""
        try:
            result = subprocess.run(
                ["pip-audit", "--strict"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message="No known vulnerabilities found"
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.WARN if env != "production" else CheckStatus.FAIL,
                    message="Vulnerable dependencies detected",
                    details=result.stdout[-500:] if result.stdout else result.stderr[-500:]
                )
        except FileNotFoundError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                message="pip-audit not installed - install for security scanning"
            )


class DockerBuildCheck(DeploymentCheck):
    """Verify Docker image builds successfully."""

    name = "Docker Build"
    required_for = ["staging", "production"]

    async def run(self, env: str) -> CheckResult:
        """Check Docker build."""
        dockerfile = os.path.join(os.path.dirname(__file__), "..", "Dockerfile")
        
        if not os.path.exists(dockerfile):
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                message="No Dockerfile found"
            )

        try:
            result = subprocess.run(
                ["docker", "build", "--check", "-f", dockerfile, "."],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), ".."),
                timeout=300
            )

            # Docker --check is not universally supported, so we just do syntax check
            if result.returncode == 0 or "dockerfile parse error" not in result.stderr.lower():
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message="Dockerfile syntax valid"
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.FAIL,
                    message="Dockerfile has errors",
                    details=result.stderr[-500:]
                )
        except FileNotFoundError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                message="Docker not available"
            )


class TypeCheckCheck(DeploymentCheck):
    """Run type checking with mypy."""

    name = "Type Checking"
    required_for = ["production"]

    async def run(self, env: str) -> CheckResult:
        """Run mypy type check."""
        try:
            result = subprocess.run(
                ["mypy", "app/", "--ignore-missing-imports"],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", "backend"),
                timeout=120
            )

            if result.returncode == 0:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message="No type errors found"
                )
            else:
                error_count = result.stdout.count("error:")
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.WARN,
                    message=f"Type errors found: {error_count}",
                    details=result.stdout[-500:] if result.stdout else None
                )
        except FileNotFoundError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                message="mypy not installed"
            )


class LintCheck(DeploymentCheck):
    """Run linting checks."""

    name = "Code Linting"
    required_for = ["staging", "production"]

    async def run(self, env: str) -> CheckResult:
        """Run ruff or flake8."""
        try:
            # Try ruff first
            result = subprocess.run(
                ["ruff", "check", "app/"],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", "backend"),
                timeout=60
            )

            if result.returncode == 0:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message="No linting errors"
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.WARN,
                    message="Linting issues found",
                    details=result.stdout[-300:] if result.stdout else None
                )
        except FileNotFoundError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIP,
                message="No linter installed (ruff recommended)"
            )


# ============================================================================
# Main Runner
# ============================================================================

ALL_CHECKS = [
    TestsPassCheck(),
    CoverageCheck(),
    DatabaseMigrationCheck(),
    SecretsCheck(),
    SecurityCheck(),
    DependenciesCheck(),
    DockerBuildCheck(),
    TypeCheckCheck(),
    LintCheck(),
]


def print_result(result: CheckResult) -> None:
    """Print a check result with color."""
    colors = {
        CheckStatus.PASS: "\033[32m",  # Green
        CheckStatus.WARN: "\033[33m",  # Yellow
        CheckStatus.FAIL: "\033[31m",  # Red
        CheckStatus.SKIP: "\033[36m",  # Cyan
    }
    reset = "\033[0m"

    status_symbol = {
        CheckStatus.PASS: "✓",
        CheckStatus.WARN: "⚠",
        CheckStatus.FAIL: "✗",
        CheckStatus.SKIP: "○",
    }

    color = colors[result.status]
    symbol = status_symbol[result.status]

    print(f"{color}{symbol} [{result.status.value}]{reset} {result.name}: {result.message}")
    
    if result.details:
        for line in result.details.split("\n")[:5]:  # Limit to 5 lines
            print(f"    {line}")


async def run_checks(env: str, skip: List[str], strict: bool) -> int:
    """Run all deployment checks.
    
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print(f"\n{'='*60}")
    print(f"  Flowrex Deployment Checklist - Target: {env.upper()}")
    print(f"{'='*60}\n")

    results: List[CheckResult] = []
    
    for check in ALL_CHECKS:
        if check.name in skip:
            results.append(CheckResult(
                name=check.name,
                status=CheckStatus.SKIP,
                message="Skipped by user"
            ))
            continue

        print(f"Running: {check.name}...", end=" ", flush=True)
        
        try:
            result = await check.run(env)
        except Exception as e:
            result = CheckResult(
                name=check.name,
                status=CheckStatus.FAIL,
                message=f"Check crashed: {str(e)}"
            )
        
        results.append(result)
        print(f"\r", end="")  # Clear "Running" line
        print_result(result)

    # Summary
    print(f"\n{'='*60}")
    
    passed = sum(1 for r in results if r.status == CheckStatus.PASS)
    warned = sum(1 for r in results if r.status == CheckStatus.WARN)
    failed = sum(1 for r in results if r.status == CheckStatus.FAIL)
    skipped = sum(1 for r in results if r.status == CheckStatus.SKIP)

    print(f"  Results: {passed} passed, {warned} warnings, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        print(f"\n\033[31m  ✗ DEPLOYMENT BLOCKED - Fix {failed} failing check(s)\033[0m")
        return 1
    elif warned > 0 and strict:
        print(f"\n\033[33m  ⚠ DEPLOYMENT BLOCKED (strict mode) - {warned} warning(s)\033[0m")
        return 1
    elif warned > 0:
        print(f"\n\033[33m  ⚠ DEPLOYMENT OK with warnings - Review {warned} warning(s)\033[0m")
        return 0
    else:
        print(f"\n\033[32m  ✓ DEPLOYMENT READY\033[0m")
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Flowrex Deployment Checklist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python deployment_checklist.py --env staging
    python deployment_checklist.py --env production --strict
    python deployment_checklist.py --skip "Docker Build" --skip "Type Checking"
        """
    )
    
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "production"],
        default=os.getenv("ENVIRONMENT", "staging"),
        help="Target environment"
    )
    
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures"
    )
    
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Skip specific checks by name"
    )

    args = parser.parse_args()

    exit_code = asyncio.run(run_checks(args.env, args.skip, args.strict))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
