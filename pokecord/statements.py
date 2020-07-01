POKECORD_CREATE_POKECORD_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL UNIQUE,
    pokemon JSON,
    PRIMARY KEY (user_id, message_id)
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

INSERT_POKEMON = """
INSERT INTO users (user_id, message_id, pokemon)
VALUES (?, ?, ?);
"""

SELECT_POKEMON = """
SELECT pokemon, message_id from users where user_id = ?
"""

UPDATE_POKEMON = """
INSERT INTO users (user_id, message_id, pokemon)
VALUES (?, ?, ?)
ON CONFLICT (message_id) DO UPDATE SET 
    pokemon = excluded.pokemon;
"""
