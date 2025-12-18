# Server Configuration
from pathlib import Path

# Get the server directory (where config.py is located)
SERVER_DIR = Path(__file__).parent.resolve()

# Network Settings
LOBBY_HOST = '0.0.0.0'
LOBBY_PORT = 8888
DEVELOPER_PORT = 8889
GAME_SERVER_START_PORT = 9000

# Database Settings
DB_PATH = str(SERVER_DIR / 'database' / 'game_store.db')

# File Storage (use absolute paths)
GAMES_DIR = str(SERVER_DIR / 'games')
PLUGINS_DIR = str(SERVER_DIR / 'plugins')
TEMP_DIR = str(SERVER_DIR / 'temp')

# Security
SECRET_KEY = 'your-secret-key-change-in-production'
PASSWORD_SALT = 'game-store-salt-2024'

# File Transfer
CHUNK_SIZE = 8192  # 8KB chunks
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Session
SESSION_TIMEOUT = 3600  # 1 hour

# Logging
LOG_LEVEL = 'INFO'
LOG_FILE = str(SERVER_DIR / 'logs' / 'server.log')