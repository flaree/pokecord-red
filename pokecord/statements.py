from typing import Final

POKECORD_CREATE_USERS_TABLE: Final[
    str
] = """
CREATE TABLE IF NOT EXISTS users (
    author_id INTEGER NOT NULL,
    pokemon JSON,
    PRIMARY KEY (author_id)
);
"""

POKECORD_CREATE_members_TABLE: Final[
    str
] = """
CREATE TABLE IF NOT EXISTS members (
    author_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    pokemon JSON,
    PRIMARY KEY (guild_id, author_id)
);
"""
PRAGMA_journal_mode = """
PRAGMA journal_mode = wal;
"""
PRAGMA_wal_autocheckpoint = """
PRAGMA wal_autocheckpoint;
"""
PRAGMA_read_uncommitted = """
PRAGMA read_uncommitted = 1;
"""
