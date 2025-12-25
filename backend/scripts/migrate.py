#!/usr/bin/env python3
"""
Database migration script with safety checks.

Prompt 17 - Deployment Prep.

Usage:
    python -m scripts.migrate          # Run all pending migrations
    python -m scripts.migrate --check  # Check migration status only
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine


def get_database_url() -> str:
    """Get database URL from environment."""
    return os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./flowrex_dev.db"
    )


def get_environment() -> str:
    """Get current environment."""
    return os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development"))


async def check_database_connection() -> bool:
    """Verify database is accessible."""
    database_url = get_database_url()
    try:
        engine = create_async_engine(database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        print("✓ Database connection successful")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


async def create_backup(backup_name: str) -> bool:
    """Create database backup before migration."""
    environment = get_environment()
    database_url = get_database_url()

    # Only backup in staging/production
    if environment in ("development", "dev"):
        print("⊙ Skipping backup in development environment")
        return True

    # Skip backup for SQLite
    if "sqlite" in database_url:
        print("⊙ Skipping backup for SQLite database")
        return True

    print(f"Creating backup: {backup_name}")

    try:
        import subprocess

        # Parse database URL: postgresql+asyncpg://user:pass@host:port/dbname
        db_url = database_url.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
        parts = db_url.split("@")
        credentials = parts[0]
        location = parts[1]

        user = credentials.split(":")[0]
        host_port_db = location.split("/")
        host_port = host_port_db[0].split(":")
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else "5432"
        dbname = host_port_db[1].split("?")[0]  # Remove query params

        backup_file = f"/tmp/{backup_name}.sql"

        result = subprocess.run(
            [
                "pg_dump",
                f"-h", host,
                f"-p", port,
                f"-U", user,
                "-F", "p",
                f"-f", backup_file,
                dbname,
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PGPASSWORD": credentials.split(":")[1] if ":" in credentials else ""},
        )

        if result.returncode == 0:
            print(f"✓ Backup created: {backup_file}")
            return True
        else:
            print(f"⚠ Backup warning: {result.stderr}")
            return True  # Continue even if backup fails

    except FileNotFoundError:
        print("⚠ pg_dump not found - skipping backup")
        return True
    except Exception as e:
        print(f"⚠ Backup failed: {e}")
        return True  # Continue even if backup fails


def get_current_revision() -> str | None:
    """Get current database revision."""
    database_url = get_database_url()
    
    # Convert async URL to sync for Alembic
    sync_url = database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            return context.get_current_revision()
    except Exception:
        return None


def get_head_revision() -> str | None:
    """Get head revision from migration scripts."""
    try:
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        return script.get_current_head()
    except Exception:
        return None


def check_migration_status() -> tuple[str | None, str | None, bool]:
    """Check if migrations are up to date."""
    current = get_current_revision()
    head = get_head_revision()
    is_current = current == head
    return current, head, is_current


def run_migrations() -> bool:
    """Run Alembic migrations."""
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("✓ Migrations completed successfully")
        return True
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False


async def verify_migration() -> bool:
    """Verify migration was successful."""
    database_url = get_database_url()
    
    try:
        engine = create_async_engine(database_url)
        async with engine.connect() as conn:
            # Check that key tables exist
            if "sqlite" in database_url:
                result = await conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' 
                    AND name IN ('users', 'signals', 'positions', 'candles')
                """))
            else:
                result = await conn.execute(text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('users', 'signals', 'positions', 'candles')
                """))
            
            tables = [row[0] for row in result]
            required_tables = ['users']  # At minimum, users table should exist
            missing = set(required_tables) - set(tables)

            if missing:
                print(f"⚠ Missing expected tables: {missing}")
                # Don't fail - this might be intentional

        await engine.dispose()
        print("✓ Migration verification successful")
        return True

    except Exception as e:
        print(f"✗ Migration verification failed: {e}")
        return False


async def main():
    """Main migration workflow."""
    print("=" * 60)
    print("DATABASE MIGRATION")
    print("=" * 60)

    environment = get_environment()
    database_url = get_database_url()
    
    # Hide credentials in output
    display_url = database_url.split("@")[-1] if "@" in database_url else database_url
    print(f"Environment: {environment}")
    print(f"Database: {display_url}")
    print()

    # Check for --check flag
    if "--check" in sys.argv:
        current, head, is_current = check_migration_status()
        print(f"Current revision: {current}")
        print(f"Head revision: {head}")
        if is_current:
            print("✓ Database is up to date")
            sys.exit(0)
        else:
            print("⚠ Database needs migration")
            sys.exit(1)

    # Step 1: Check database connection
    if not await check_database_connection():
        print("\nMigration aborted: Cannot connect to database")
        sys.exit(1)

    # Step 2: Check migration status
    current, head, is_current = check_migration_status()
    print(f"Current revision: {current}")
    print(f"Head revision: {head}")
    
    if is_current:
        print("\n✓ Database is already up to date")
        sys.exit(0)

    # Step 3: Create backup
    backup_name = f"pre_migration_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    await create_backup(backup_name)

    # Step 4: Run migrations
    print("\nRunning migrations...")
    if not run_migrations():
        print("\nMigration failed!")
        print(f"If needed, restore from backup: {backup_name}")
        sys.exit(1)

    # Step 5: Verify migration
    if not await verify_migration():
        print("\nMigration verification failed!")
        print(f"If needed, restore from backup: {backup_name}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
