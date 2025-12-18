"""
Database Schema - Separate Developer and Player Accounts
"""
import sqlite3
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def create_database(db_path):
    """Create database with separated account types"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Developer accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS developers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Player accounts table  
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Games table - reference to developer
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            developer_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            version TEXT NOT NULL,
            min_players INTEGER NOT NULL,
            max_players INTEGER NOT NULL,
            game_type TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            downloads INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (developer_id) REFERENCES developers(id),
            UNIQUE(name, version)
        )
    ''')
    
    # Player downloads table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            version TEXT NOT NULL,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players(id),
            FOREIGN KEY (game_id) REFERENCES games(id),
            UNIQUE(player_id, game_id)
        )
    ''')
    
    # Rooms table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT UNIQUE NOT NULL,
            game_id INTEGER NOT NULL,
            room_name TEXT NOT NULL,
            host_player_id INTEGER NOT NULL,
            max_players INTEGER NOT NULL,
            current_players INTEGER DEFAULT 1,
            status TEXT DEFAULT 'waiting',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id),
            FOREIGN KEY (host_player_id) REFERENCES players(id)
        )
    ''')
    
    # Room members table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms(id),
            FOREIGN KEY (player_id) REFERENCES players(id),
            UNIQUE(room_id, player_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info("Database created with separated account types")


def hash_password(password, salt="game-store-salt-2024"):
    """Hash password"""
    return hashlib.sha256((password + salt).encode()).hexdigest()


def migrate_existing_database(db_path):
    """Migrate existing database to new schema"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if old 'users' table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone():
        logger.info("Migrating existing database...")
        
        # Get all users
        cursor.execute("SELECT id, username, password_hash, email, created_at FROM users")
        users = cursor.fetchall()
        
        # Create new tables
        create_database(db_path)
        
        # Migrate users - assume first few are developers, rest are players
        for user_id, username, password_hash, email, created_at in users:
            # Simple heuristic: if username starts with 'dev', it's a developer
            if username.lower().startswith('dev'):
                cursor.execute('''
                    INSERT OR IGNORE INTO developers (username, password_hash, email, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (username, password_hash, email, created_at))
            else:
                cursor.execute('''
                    INSERT OR IGNORE INTO players (username, password_hash, email, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (username, password_hash, email, created_at))
        
        conn.commit()
        logger.info("Migration completed")
    
    conn.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = '../server/database/game_store.db'
    
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Check if migration needed
    if Path(db_path).exists():
        print(f"Database exists at {db_path}")
        print("Migrating to new schema...")
        migrate_existing_database(db_path)
    else:
        print(f"Creating new database at {db_path}")
        create_database(db_path)
    
    print("Done!")