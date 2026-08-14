import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = [
    ROOT / "migrations/0001_universe_versions.sql",
    ROOT / "migrations/0002_versioned_source_metadata.sql",
    ROOT / "migrations/0003_nasdaq_giw_metadata.sql",
    ROOT / "migrations/0004_universe_point_in_time_archive.sql",
]


def apply_migrations(connection):
    for path in MIGRATIONS:
        connection.executescript(path.read_text(encoding="utf-8"))


def insert_version(connection, *, version_id, version, source_as_of, tickers, status="staging"):
    connection.execute(
        """
        INSERT INTO universe_versions (
          id, universe_id, version, source_as_of, fetched_at, source_url,
          checksum, member_count, status, warning, source_label, is_proxy
        ) VALUES (?, 'sp500', ?, ?, ?, 'https://example.com/source', ?, ?, ?, NULL, 'Fixture', 0)
        """,
        (
            version_id,
            version,
            source_as_of,
            f"{source_as_of}T12:00:00Z",
            f"checksum-{version}",
            len(tickers),
            status,
        ),
    )
    for ticker in tickers:
        connection.execute(
            "INSERT INTO universe_members (version_id, ticker, source_ticker) VALUES (?, ?, ?)",
            (version_id, ticker, ticker),
        )


def test_migration_seeds_retained_snapshots_with_canonical_membership_json():
    connection = sqlite3.connect(":memory:")
    try:
        for path in MIGRATIONS[:3]:
            connection.executescript(path.read_text(encoding="utf-8"))
        insert_version(
            connection,
            version_id="existing",
            version="2026-08-10-existing",
            source_as_of="2026-08-10",
            tickers=["MSFT", "AAPL"],
            status="archived",
        )

        connection.executescript(MIGRATIONS[3].read_text(encoding="utf-8"))
        row = connection.execute(
            """
            SELECT source_as_of, member_count, members_json
            FROM universe_snapshot_archive
            WHERE universe_id = 'sp500' AND version = '2026-08-10-existing'
            """
        ).fetchone()

        assert row[:2] == ("2026-08-10", 2)
        assert json.loads(row[2]) == ["AAPL", "MSFT"]
    finally:
        connection.close()


def test_activation_trigger_archives_members_before_retention_can_delete_version():
    connection = sqlite3.connect(":memory:")
    try:
        apply_migrations(connection)
        insert_version(
            connection,
            version_id="new-version",
            version="2026-08-14-new",
            source_as_of="2026-08-14",
            tickers=["BBB", "AAA"],
        )

        connection.execute(
            "UPDATE universe_versions SET status = 'active' WHERE id = 'new-version'"
        )
        row = connection.execute(
            """
            SELECT checksum, member_count, members_json, archive_format_version
            FROM universe_snapshot_archive
            WHERE universe_id = 'sp500' AND version = '2026-08-14-new'
            """
        ).fetchone()

        assert row[0] == "checksum-2026-08-14-new"
        assert row[1] == 2
        assert json.loads(row[2]) == ["AAA", "BBB"]
        assert row[3] == "universe-members-json-v1"

        connection.execute("DELETE FROM universe_members WHERE version_id = 'new-version'")
        connection.execute("DELETE FROM universe_versions WHERE id = 'new-version'")
        archived = connection.execute(
            "SELECT members_json FROM universe_snapshot_archive WHERE universe_id = 'sp500'"
        ).fetchone()
        assert json.loads(archived[0]) == ["AAA", "BBB"]
    finally:
        connection.close()
