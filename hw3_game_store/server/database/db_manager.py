"""
Database Manager with connection pooling and helper methods
"""
import sqlite3
import hashlib
import secrets
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import threading

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Thread-safe SQLite database manager"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._initialize_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection
    
    def _initialize_database(self):
        """Initialize database with schema"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        schema_path = Path(__file__).parent / 'schema.sql'
        with open(schema_path, 'r') as f:
            schema = f.read()
        
        conn = sqlite3.connect(self.db_path)
        conn.executescript(schema)
        conn.commit()
        conn.close()
        
        logger.info(f"Database initialized at {self.db_path}")
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return cursor"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            # Only commit for write operations
            if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')):
                conn.commit()
            return cursor
        except Exception as e:
            conn.rollback()
            logger.error(f"Query error: {e}\nQuery: {query}\nParams: {params}")
            raise
    
    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Execute query and fetch one result"""
        cursor = self.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def fetchall(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query and fetch all results"""
        cursor = self.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    # User Management (Legacy - for backward compatibility)
    
    @staticmethod
    def hash_password(password: str, salt: str = "game-store-2024") -> str:
        """Hash password with salt"""
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    
    def create_user(self, username: str, password: str, user_type: str = 'player') -> Optional[int]:
        """Create new user (Legacy method - kept for backward compatibility)"""
        try:
            password_hash = self.hash_password(password)
            cursor = self.execute(
                "INSERT INTO users (username, password_hash, user_type) VALUES (?, ?, ?)",
                (username, password_hash, user_type)
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"User {username} already exists")
            return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user info (Legacy method)"""
        password_hash = self.hash_password(password)
        user = self.fetchone(
            "SELECT * FROM users WHERE username = ? AND password_hash = ?",
            (username, password_hash)
        )
        
        if user:
            self.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user['id'],)
            )
        
        return user
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID (Legacy method)"""
        return self.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    
    # Developer Management (NEW)
    
    def create_developer(self, username: str, password: str, email: str = None) -> Optional[int]:
        """Create new developer account"""
        try:
            password_hash = self.hash_password(password)
            cursor = self.execute(
                "INSERT INTO developers (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email)
            )
            logger.info(f"Developer created: {username}")
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Developer {username} already exists")
            return None
    
    def authenticate_developer(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate developer and return developer info"""
        password_hash = self.hash_password(password)
        developer = self.fetchone(
            "SELECT * FROM developers WHERE username = ? AND password_hash = ?",
            (username, password_hash)
        )
        
        if developer:
            self.execute(
                "UPDATE developers SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (developer['id'],)
            )
            logger.info(f"Developer authenticated: {username}")
        
        return developer
    
    def get_developer(self, developer_id: int) -> Optional[Dict]:
        """Get developer by ID"""
        return self.fetchone("SELECT * FROM developers WHERE id = ?", (developer_id,))
    
    # Player Management (NEW)
    
    def create_player(self, username: str, password: str, email: str = None) -> Optional[int]:
        """Create new player account"""
        try:
            password_hash = self.hash_password(password)
            cursor = self.execute(
                "INSERT INTO players (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email)
            )
            logger.info(f"Player created: {username}")
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Player {username} already exists")
            return None
    
    def authenticate_player(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate player and return player info"""
        password_hash = self.hash_password(password)
        player = self.fetchone(
            "SELECT * FROM players WHERE username = ? AND password_hash = ?",
            (username, password_hash)
        )
        
        if player:
            self.execute(
                "UPDATE players SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (player['id'],)
            )
            logger.info(f"Player authenticated: {username}")
        
        return player
    
    def get_player(self, player_id: int) -> Optional[Dict]:
        """Get player by ID"""
        return self.fetchone("SELECT * FROM players WHERE id = ?", (player_id,))
    
    # Session Management (Legacy)
    
    def create_session(self, user_id: int, duration_hours: int = 24) -> str:
        """Create session token (Legacy)"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        self.execute(
            "INSERT INTO sessions (user_id, session_token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at.isoformat())
        )
        
        return token
    
    def validate_session(self, token: str) -> Optional[Dict]:
        """Validate session and return user info (Legacy)"""
        session = self.fetchone(
            "SELECT s.*, u.* FROM sessions s JOIN users u ON s.user_id = u.id "
            "WHERE s.session_token = ? AND s.expires_at > datetime('now')",
            (token,)
        )
        return session
    
    def delete_session(self, token: str):
        """Delete session (Legacy)"""
        self.execute("DELETE FROM sessions WHERE session_token = ?", (token,))
    
    # Developer Session Management (NEW)
    
    def create_developer_session(self, developer_id: int, duration_hours: int = 24) -> str:
        """Create developer session token"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        self.execute(
            "INSERT INTO developer_sessions (developer_id, session_token, expires_at) VALUES (?, ?, ?)",
            (developer_id, token, expires_at.isoformat())
        )
        
        return token
    
    def validate_developer_session(self, token: str) -> Optional[Dict]:
        """Validate developer session and return developer info"""
        session = self.fetchone(
            "SELECT s.*, d.* FROM developer_sessions s JOIN developers d ON s.developer_id = d.id "
            "WHERE s.session_token = ? AND s.expires_at > datetime('now')",
            (token,)
        )
        return session
    
    def delete_developer_session(self, token: str):
        """Delete developer session"""
        self.execute("DELETE FROM developer_sessions WHERE session_token = ?", (token,))
    
    # Player Session Management (NEW)
    
    def create_player_session(self, player_id: int, duration_hours: int = 24) -> str:
        """Create player session token"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        self.execute(
            "INSERT INTO player_sessions (player_id, session_token, expires_at) VALUES (?, ?, ?)",
            (player_id, token, expires_at.isoformat())
        )
        
        return token
    
    def validate_player_session(self, token: str) -> Optional[Dict]:
        """Validate player session and return player info"""
        session = self.fetchone(
            "SELECT s.*, p.* FROM player_sessions s JOIN players p ON s.player_id = p.id "
            "WHERE s.session_token = ? AND s.expires_at > datetime('now')",
            (token,)
        )
        return session
    
    def delete_player_session(self, token: str):
        """Delete player session"""
        self.execute("DELETE FROM player_sessions WHERE session_token = ?", (token,))
    
    # Game Management
    
    def create_game(self, name: str, description: str, developer_id: int,
                   version: str, min_players: int, max_players: int,
                   game_type: str = 'cli') -> Optional[int]:
        """Create new game"""
        try:
            cursor = self.execute(
                """INSERT INTO games 
                (name, description, developer_id, current_version, 
                 min_players, max_players, game_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, description, developer_id, version, 
                 min_players, max_players, game_type)
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Game {name} already exists")
            return None
    
    def get_game(self, game_id: int) -> Optional[Dict]:
        """Get game by ID"""
        return self.fetchone("SELECT * FROM games WHERE id = ?", (game_id,))
    
    def get_active_games(self) -> List[Dict]:
        """Get all active games"""
        return self.fetchall("SELECT * FROM games WHERE status = 'active' ORDER BY download_count DESC")
    
    def get_games_by_developer(self, developer_id: int) -> List[Dict]:
        """Get games by developer"""
        return self.fetchall(
            "SELECT * FROM games WHERE developer_id = ? ORDER BY created_at DESC",
            (developer_id,)
        )
    
    def update_game_status(self, game_id: int, status: str) -> bool:
        """Update game status (active/inactive)"""
        cursor = self.execute(
            "UPDATE games SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, game_id)
        )
        return cursor.rowcount > 0
    
    def update_game_version(self, game_id: int, new_version: str) -> bool:
        """Update game current version"""
        cursor = self.execute(
            "UPDATE games SET current_version = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_version, game_id)
        )
        return cursor.rowcount > 0
    
    def increment_download_count(self, game_id: int):
        """Increment game download count"""
        self.execute(
            "UPDATE games SET download_count = download_count + 1 WHERE id = ?",
            (game_id,)
        )
    
    # Game Versions
    
    def add_game_version(self, game_id: int, version: str, changelog: str,
                        file_path: str, file_size: int, checksum: str) -> Optional[int]:
        """Add new game version"""
        try:
            cursor = self.execute(
                """INSERT INTO game_versions 
                (game_id, version, changelog, file_path, file_size, checksum)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (game_id, version, changelog, file_path, file_size, checksum)
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Version {version} for game {game_id} already exists")
            return None
    
    def get_game_version(self, game_id: int, version: str) -> Optional[Dict]:
        """Get specific game version"""
        return self.fetchone(
            "SELECT * FROM game_versions WHERE game_id = ? AND version = ?",
            (game_id, version)
        )
    
    def get_latest_version(self, game_id: int) -> Optional[Dict]:
        """Get latest version of a game"""
        return self.fetchone(
            "SELECT * FROM game_versions WHERE game_id = ? ORDER BY created_at DESC LIMIT 1",
            (game_id,)
        )
    
    # Downloads (Updated to use player_id)
    
    def record_download(self, game_id: int, player_id: int, version: str):
        """Record a download"""
        self.execute(
            "INSERT INTO downloads (game_id, player_id, version) VALUES (?, ?, ?)",
            (game_id, player_id, version)
        )
        self.increment_download_count(game_id)
    
    def get_player_downloads(self, player_id: int) -> List[Dict]:
        """Get player's download history"""
        return self.fetchall(
            """SELECT d.*, g.name as game_name, g.current_version
            FROM downloads d JOIN games g ON d.game_id = g.id
            WHERE d.player_id = ? ORDER BY d.downloaded_at DESC""",
            (player_id,)
        )
    
    # Reviews (Updated to use player_id)
    
    def add_review(self, game_id: int, player_id: int, rating: int, comment: str = "") -> bool:
        """Add or update review"""
        try:
            self.execute(
                """INSERT INTO reviews (game_id, player_id, rating, comment)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(game_id, player_id) DO UPDATE SET
                rating = excluded.rating,
                comment = excluded.comment,
                updated_at = CURRENT_TIMESTAMP""",
                (game_id, player_id, rating, comment)
            )
            return True
        except Exception as e:
            logger.error(f"Error adding review: {e}")
            return False
    
    def get_game_reviews(self, game_id: int, limit: int = 20) -> List[Dict]:
        """Get reviews for a game"""
        return self.fetchall(
            """SELECT r.*, p.username 
            FROM reviews r JOIN players p ON r.player_id = p.id
            WHERE r.game_id = ? ORDER BY r.created_at DESC LIMIT ?""",
            (game_id, limit)
        )
    
    # Rooms (Updated to use player_id)
    
    def create_room(self, game_id: int, host_id: int, name: str, max_players: int) -> Optional[int]:
        """Create game room"""
        room_code = secrets.token_hex(4).upper()
        try:
            cursor = self.execute(
                """INSERT INTO rooms (game_id, host_id, name, room_code, max_players)
                VALUES (?, ?, ?, ?, ?)""",
                (game_id, host_id, name, room_code, max_players)
            )
            room_id = cursor.lastrowid
            
            # Add host as first player
            self.execute(
                "INSERT INTO room_players (room_id, player_id) VALUES (?, ?)",
                (room_id, host_id)
            )
            
            return room_id
        except Exception as e:
            logger.error(f"Error creating room: {e}")
            return None
    
    def get_room(self, room_id: int) -> Optional[Dict]:
        """Get room info"""
        return self.fetchone("SELECT * FROM rooms WHERE id = ?", (room_id,))
    
    def get_active_rooms(self) -> List[Dict]:
        """Get all active rooms (exclude rooms older than 10 minutes in waiting status)"""
        return self.fetchall(
            """SELECT r.*, g.name as game_name, p.username as host_name
            FROM rooms r 
            JOIN games g ON r.game_id = g.id
            JOIN players p ON r.host_id = p.id
            WHERE r.status IN ('waiting', 'playing')
              AND (
                r.status = 'playing' OR
                datetime(r.created_at, '+10 minutes') > datetime('now')
              )
            ORDER BY r.created_at DESC"""
        )
    
    def join_room(self, room_id: int, player_id: int) -> bool:
        """Add player to room"""
        try:
            self.execute(
                "INSERT INTO room_players (room_id, player_id) VALUES (?, ?)",
                (room_id, player_id)
            )
            return True
        except sqlite3.IntegrityError:
            return False
    
    def leave_room(self, room_id: int, player_id: int):
        """Remove player from room"""
        self.execute(
            "DELETE FROM room_players WHERE room_id = ? AND player_id = ?",
            (room_id, player_id)
        )
    
    def update_room_status(self, room_id: int, status: str, game_port: int = None):
        """Update room status"""
        if game_port:
            self.execute(
                "UPDATE rooms SET status = ?, game_port = ? WHERE id = ?",
                (status, game_port, room_id)
            )
        else:
            self.execute(
                "UPDATE rooms SET status = ? WHERE id = ?",
                (status, room_id)
            )
    
    def get_room_players(self, room_id: int) -> List[Dict]:
        """Get players in a room"""
        return self.fetchall(
            """SELECT p.id, p.username 
            FROM room_players rp JOIN players p ON rp.player_id = p.id
            WHERE rp.room_id = ?""",
            (room_id,)
        )
    
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()