-- Game Store Database Schema - Separated Accounts
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Developers Table (separate from players)
CREATE TABLE IF NOT EXISTS developers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_developers_username ON developers(username);

-- Players Table (separate from developers)
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_players_username ON players(username);

-- Games Table
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    developer_id INTEGER NOT NULL,
    current_version TEXT NOT NULL DEFAULT '1.0.0',
    min_players INTEGER DEFAULT 2,
    max_players INTEGER DEFAULT 2,
    game_type TEXT DEFAULT 'cli' CHECK(game_type IN ('cli', 'gui')),
    average_rating REAL DEFAULT 0.0,
    rating_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (developer_id) REFERENCES developers(id)
);

CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_developer ON games(developer_id);

-- Game Versions Table
CREATE TABLE IF NOT EXISTS game_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    changelog TEXT,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    checksum TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    UNIQUE(game_id, version)
);

CREATE INDEX IF NOT EXISTS idx_versions_game ON game_versions(game_id);

-- Downloads Table (references players table)
CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id),
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE INDEX IF NOT EXISTS idx_downloads_player ON downloads(player_id);
CREATE INDEX IF NOT EXISTS idx_downloads_game ON downloads(game_id);

-- Reviews Table (references players table)
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id),
    UNIQUE(game_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_game ON reviews(game_id);
CREATE INDEX IF NOT EXISTS idx_reviews_player ON reviews(player_id);

-- Rooms Table (references players table)
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    room_code TEXT UNIQUE,
    max_players INTEGER DEFAULT 4,
    current_players INTEGER DEFAULT 1,
    status TEXT DEFAULT 'waiting' CHECK(status IN ('waiting', 'playing', 'closed')),
    game_port INTEGER,
    game_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id),
    FOREIGN KEY (host_id) REFERENCES players(id)
);

CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
CREATE INDEX IF NOT EXISTS idx_rooms_game ON rooms(game_id);

-- Room Players Table (references players table)
CREATE TABLE IF NOT EXISTS room_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id),
    UNIQUE(room_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_room_players_room ON room_players(room_id);

-- Developer Sessions Table
CREATE TABLE IF NOT EXISTS developer_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    developer_id INTEGER NOT NULL,
    session_token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (developer_id) REFERENCES developers(id)
);

CREATE INDEX IF NOT EXISTS idx_dev_sessions_token ON developer_sessions(session_token);

-- Player Sessions Table
CREATE TABLE IF NOT EXISTS player_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    session_token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE INDEX IF NOT EXISTS idx_player_sessions_token ON player_sessions(session_token);

-- Trigger: Update game rating when new review added
CREATE TRIGGER IF NOT EXISTS update_game_rating_insert 
AFTER INSERT ON reviews
BEGIN
    UPDATE games SET 
        average_rating = (SELECT AVG(rating) FROM reviews WHERE game_id = NEW.game_id),
        rating_count = (SELECT COUNT(*) FROM reviews WHERE game_id = NEW.game_id),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.game_id;
END;

-- Trigger: Update game rating when review updated
CREATE TRIGGER IF NOT EXISTS update_game_rating_update 
AFTER UPDATE ON reviews
BEGIN
    UPDATE games SET 
        average_rating = (SELECT AVG(rating) FROM reviews WHERE game_id = NEW.game_id),
        rating_count = (SELECT COUNT(*) FROM reviews WHERE game_id = NEW.game_id),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.game_id;
END;

-- Trigger: Update game rating when review deleted
CREATE TRIGGER IF NOT EXISTS update_game_rating_delete 
AFTER DELETE ON reviews
BEGIN
    UPDATE games SET 
        average_rating = COALESCE((SELECT AVG(rating) FROM reviews WHERE game_id = OLD.game_id), 0.0),
        rating_count = (SELECT COUNT(*) FROM reviews WHERE game_id = OLD.game_id),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.game_id;
END;

-- Trigger: Update room player count
CREATE TRIGGER IF NOT EXISTS update_room_players_insert
AFTER INSERT ON room_players
BEGIN
    UPDATE rooms SET 
        current_players = (SELECT COUNT(*) FROM room_players WHERE room_id = NEW.room_id)
    WHERE id = NEW.room_id;
END;

CREATE TRIGGER IF NOT EXISTS update_room_players_delete
AFTER DELETE ON room_players
BEGIN
    UPDATE rooms SET 
        current_players = (SELECT COUNT(*) FROM room_players WHERE room_id = OLD.room_id)
    WHERE id = OLD.room_id;
END;