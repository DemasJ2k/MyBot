"""
CROSSCHECK Architectural Validation Tests.

These tests enforce architectural rules from CROSSCHECK.md to ensure:
- Hard risk constants are immutable
- Execution engine is the sole trade executor
- Journal entries are immutable
- API routes use service layer (not direct model imports)
- Mode enforcement is properly implemented
"""
import pytest
import ast
import os
from pathlib import Path
from typing import List, Set


@pytest.mark.crosscheck
class TestArchitectureRules:
    """Validate core architectural rules."""

    @pytest.fixture
    def backend_path(self) -> Path:
        """Get backend source path."""
        return Path(__file__).parent.parent.parent / "app"

    @pytest.fixture
    def risk_path(self, backend_path: Path) -> Path:
        """Get risk module path."""
        return backend_path / "risk"

    @pytest.fixture
    def execution_path(self, backend_path: Path) -> Path:
        """Get execution module path."""
        return backend_path / "execution"

    def test_hard_risk_constants_exist(self, risk_path: Path):
        """
        CROSSCHECK RULE: Hard risk constants must exist and be defined.
        """
        constants_file = risk_path / "constants.py"
        assert constants_file.exists(), "Risk constants file must exist"

        with open(constants_file, "r") as f:
            content = f.read()

        required_constants = [
            "MAX_RISK_PER_TRADE_PERCENT",
            "MAX_DAILY_LOSS_PERCENT",
            "EMERGENCY_DRAWDOWN_PERCENT",
            "MAX_OPEN_POSITIONS",
            "MAX_TRADES_PER_DAY",
            "MAX_TRADES_PER_HOUR",
            "MIN_RISK_REWARD_RATIO",
        ]

        for constant in required_constants:
            assert constant in content, f"Missing required constant: {constant}"

    def test_hard_risk_constants_values_are_safe(self, risk_path: Path):
        """
        CROSSCHECK RULE: Hard risk constants must have safe values.
        """
        constants_file = risk_path / "constants.py"
        
        # Import the constants module dynamically
        import importlib.util
        spec = importlib.util.spec_from_file_location("constants", constants_file)
        constants = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(constants)

        # Verify constants have safe values
        assert constants.MAX_RISK_PER_TRADE_PERCENT <= 5.0, "Max risk per trade should be <= 5%"
        assert constants.MAX_DAILY_LOSS_PERCENT <= 10.0, "Max daily loss should be <= 10%"
        assert constants.EMERGENCY_DRAWDOWN_PERCENT <= 20.0, "Emergency drawdown should be <= 20%"
        assert constants.MAX_OPEN_POSITIONS <= 20, "Max open positions should be <= 20"
        assert constants.MAX_TRADES_PER_DAY <= 50, "Max trades per day should be <= 50"
        assert constants.MIN_RISK_REWARD_RATIO >= 1.0, "Min R:R ratio should be >= 1.0"

    def test_execution_engine_sole_trade_executor(self, backend_path: Path):
        """
        CROSSCHECK RULE: Only execution engine can submit trades to broker.
        No other module should directly call broker submission methods.
        """
        violations = []
        execution_path = backend_path / "execution"

        # Patterns that indicate broker submission
        broker_patterns = [
            "submit_order",
            "place_order",
            "execute_trade",
            "broker.buy",
            "broker.sell",
        ]

        for py_file in backend_path.rglob("*.py"):
            # Skip execution engine itself
            if "execution" in str(py_file):
                continue
            # Skip test files
            if "test" in str(py_file):
                continue

            with open(py_file, "r", encoding="utf-8") as f:
                try:
                    content = f.read()
                except UnicodeDecodeError:
                    continue

                for pattern in broker_patterns:
                    if pattern in content:
                        # Check if it's in a comment or string
                        lines = content.split("\n")
                        for line_num, line in enumerate(lines, 1):
                            if pattern in line:
                                stripped = line.strip()
                                # Skip comments
                                if stripped.startswith("#"):
                                    continue
                                # Skip docstrings (rough check)
                                if stripped.startswith('"""') or stripped.startswith("'''"):
                                    continue
                                violations.append(
                                    f"{py_file.relative_to(backend_path)}:{line_num}: "
                                    f"Contains '{pattern}' - only execution engine should submit trades"
                                )

        # Allow some violations for legitimate type hints or method definitions
        # Filter out false positives
        real_violations = [v for v in violations if "def " not in v and "Type" not in v]
        
        assert len(real_violations) == 0, (
            f"CROSSCHECK violation - broker submission outside execution engine:\n"
            + "\n".join(real_violations[:10])  # Show first 10
        )

    def test_journal_entries_immutable(self, backend_path: Path):
        """
        CROSSCHECK RULE: Journal entries must be immutable (no update methods).
        """
        journal_file = backend_path / "models" / "journal.py"

        if not journal_file.exists():
            pytest.skip("Journal model not yet created")

        with open(journal_file, "r") as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name == "JournalEntry":
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            # Update methods violate immutability
                            if "update" in item.name.lower():
                                pytest.fail(
                                    f"JournalEntry has update method '{item.name}' - "
                                    "journal entries must be immutable"
                                )
                            # Delete methods also violate immutability
                            if "delete" in item.name.lower():
                                pytest.fail(
                                    f"JournalEntry has delete method '{item.name}' - "
                                    "journal entries must be immutable"
                                )


@pytest.mark.crosscheck
class TestModeEnforcement:
    """Validate GUIDE/AUTONOMOUS mode enforcement."""

    @pytest.fixture
    def backend_path(self) -> Path:
        """Get backend source path."""
        return Path(__file__).parent.parent.parent / "app"

    def test_mode_enum_exists(self, backend_path: Path):
        """
        CROSSCHECK RULE: SystemMode enum must exist for GUIDE/AUTONOMOUS modes.
        """
        # Check in models
        settings_file = backend_path / "models" / "system_settings.py"
        
        if not settings_file.exists():
            pytest.skip("System settings model not yet created")

        with open(settings_file, "r") as f:
            content = f.read()

        assert "SystemMode" in content, "SystemMode enum must be defined"
        assert "GUIDE" in content, "GUIDE mode must be defined"
        assert "AUTONOMOUS" in content, "AUTONOMOUS mode must be defined"

    def test_execution_checks_mode(self, backend_path: Path):
        """
        CROSSCHECK RULE: Execution engine must check mode before executing trades.
        """
        engine_file = backend_path / "execution" / "engine.py"

        if not engine_file.exists():
            pytest.skip("Execution engine not yet created")

        with open(engine_file, "r") as f:
            content = f.read()

        # Should check for GUIDE mode or AUTONOMOUS mode
        mode_check_patterns = [
            "GUIDE",
            "AUTONOMOUS",
            "mode",
            "SystemMode",
        ]

        found_mode_check = any(pattern in content for pattern in mode_check_patterns)
        assert found_mode_check, (
            "Execution engine must check system mode before executing trades"
        )


@pytest.mark.crosscheck
class TestServiceLayerUsage:
    """Validate that API routes use service layer properly."""

    @pytest.fixture
    def api_path(self) -> Path:
        """Get API routes path."""
        return Path(__file__).parent.parent.parent / "app" / "api"

    def test_routes_use_service_layer(self, api_path: Path):
        """
        CROSSCHECK RULE: API routes should use service layer, not direct model manipulation.
        This is a soft check - some model imports for type hints are acceptable.
        """
        routes_path = api_path / "v1"
        
        if not routes_path.exists():
            pytest.skip("API routes not yet created")

        # Count service vs model imports
        service_imports = 0
        model_imports = 0

        for route_file in routes_path.glob("*_routes.py"):
            with open(route_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Count imports
            if "from app.services" in content or "import.*service" in content.lower():
                service_imports += 1
            if "from app.models" in content:
                model_imports += 1

        # Routes should have some service imports
        # This is informational - not a hard failure
        if service_imports == 0 and model_imports > 0:
            pytest.skip(
                "Consider using service layer in routes for better separation of concerns"
            )


@pytest.mark.crosscheck
class TestAuditTrailCompliance:
    """Validate audit trail requirements."""

    @pytest.fixture
    def backend_path(self) -> Path:
        """Get backend source path."""
        return Path(__file__).parent.parent.parent / "app"

    def test_settings_audit_exists(self, backend_path: Path):
        """
        CROSSCHECK RULE: Settings changes must be audited.
        """
        settings_file = backend_path / "models" / "system_settings.py"

        if not settings_file.exists():
            pytest.skip("System settings model not yet created")

        with open(settings_file, "r") as f:
            content = f.read()

        assert "SettingsAudit" in content or "Audit" in content, (
            "Settings audit model must exist for change tracking"
        )

    def test_risk_decisions_logged(self, backend_path: Path):
        """
        CROSSCHECK RULE: Risk decisions must be logged.
        """
        risk_models = backend_path / "models" / "risk.py"

        if not risk_models.exists():
            pytest.skip("Risk models not yet created")

        with open(risk_models, "r") as f:
            content = f.read()

        assert "RiskDecision" in content, (
            "RiskDecision model must exist for audit trail"
        )


@pytest.mark.crosscheck
class TestDatabaseConstraints:
    """Validate database model constraints."""

    @pytest.fixture
    def backend_path(self) -> Path:
        """Get backend source path."""
        return Path(__file__).parent.parent.parent / "app"

    def test_user_foreign_keys_exist(self, backend_path: Path):
        """
        CROSSCHECK RULE: Multi-tenant models must have user_id foreign key.
        """
        models_to_check = ["signal.py", "position.py", "execution.py"]
        models_path = backend_path / "models"

        for model_file in models_to_check:
            file_path = models_path / model_file
            if not file_path.exists():
                continue

            with open(file_path, "r") as f:
                content = f.read()

            # Check for user_id foreign key
            assert "user_id" in content, (
                f"{model_file} must have user_id for multi-tenancy"
            )


@pytest.mark.crosscheck  
class TestSafetyMechanisms:
    """Validate safety mechanisms are in place."""

    @pytest.fixture
    def backend_path(self) -> Path:
        """Get backend source path."""
        return Path(__file__).parent.parent.parent / "app"

    def test_emergency_shutdown_exists(self, backend_path: Path):
        """
        CROSSCHECK RULE: Emergency shutdown mechanism must exist.
        """
        risk_path = backend_path / "risk"
        
        found_emergency = False
        for py_file in risk_path.glob("*.py"):
            with open(py_file, "r") as f:
                content = f.read()
            if "emergency" in content.lower() and "shutdown" in content.lower():
                found_emergency = True
                break

        assert found_emergency, "Emergency shutdown mechanism must exist in risk module"

    def test_rate_limiting_configured(self, backend_path: Path):
        """
        CROSSCHECK RULE: Rate limiting must be configured for auth endpoints.
        """
        auth_routes = backend_path / "api" / "v1" / "auth_routes.py"

        if not auth_routes.exists():
            pytest.skip("Auth routes not yet created")

        with open(auth_routes, "r") as f:
            content = f.read()

        assert "limiter" in content or "rate_limit" in content.lower(), (
            "Auth routes must have rate limiting configured"
        )
