#!/usr/bin/env python3
"""
Database rollback script.

Prompt 17 - Deployment Prep.

Usage:
    python -m scripts.rollback          # Rollback 1 migration
    python -m scripts.rollback 3        # Rollback 3 migrations
    python -m scripts.rollback base     # Rollback all migrations
"""

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine


def get_database_url() -> str:
    """Get database URL from environment."""
    return os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./flowrex_dev.db"
    )


def get_current_revision() -> str | None:
    """Get current database revision."""
    database_url = get_database_url()
    sync_url = database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            return context.get_current_revision()
    except Exception:
        return None


def list_revisions() -> list[str]:
    """List all available revisions."""
    try:
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        revisions = []
        for rev in script.walk_revisions():
            revisions.append(f"{rev.revision}: {rev.doc or 'No description'}")
        return revisions
    except Exception as e:
        print(f"Error listing revisions: {e}")
        return []


def rollback_migration(target: str = "-1") -> bool:
    """Rollback database migration.
    
    Args:
        target: "-1" for one step, "-N" for N steps, "base" for all, or revision ID
    """
    try:
        alembic_cfg = Config("alembic.ini")
        
        current = get_current_revision()
        print(f"Current revision: {current}")
        
        if current is None:
            print("No migrations to rollback")
            return True
        
        if target == "base":
            command.downgrade(alembic_cfg, "base")
            print("✓ Rolled back all migrations")
        elif target.startswith("-"):
            command.downgrade(alembic_cfg, target)
            print(f"✓ Rolled back {target[1:]} migration(s)")
        else:
            command.downgrade(alembic_cfg, target)
            print(f"✓ Rolled back to revision: {target}")
        
        new_revision = get_current_revision()
        print(f"New revision: {new_revision}")
        
        return True

    except Exception as e:
        print(f"✗ Rollback failed: {e}")
        return False


def main():
    """Main rollback workflow."""
    print("=" * 60)
    print("DATABASE ROLLBACK")
    print("=" * 60)
    
    environment = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development"))
    print(f"Environment: {environment}")
    print()

    # Parse arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--list":
            print("Available revisions:")
            for rev in list_revisions():
                print(f"  {rev}")
            sys.exit(0)
        
        if arg == "--help":
            print("Usage:")
            print("  python -m scripts.rollback          # Rollback 1 migration")
            print("  python -m scripts.rollback 3        # Rollback 3 migrations")
            print("  python -m scripts.rollback base     # Rollback all migrations")
            print("  python -m scripts.rollback <rev>    # Rollback to specific revision")
            print("  python -m scripts.rollback --list   # List all revisions")
            sys.exit(0)
        
        if arg == "base":
            target = "base"
        elif arg.isdigit():
            target = f"-{arg}"
        else:
            target = arg
    else:
        target = "-1"

    # Confirm in production
    if environment in ("production", "prod", "staging"):
        response = input(f"\n⚠ Rolling back in {environment}! Are you sure? (yes/no): ")
        if response.lower() != "yes":
            print("Rollback aborted by user")
            sys.exit(1)

    print(f"\nRolling back: {target}")
    
    if rollback_migration(target):
        print("\n" + "=" * 60)
        print("ROLLBACK COMPLETED SUCCESSFULLY")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\nRollback failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
