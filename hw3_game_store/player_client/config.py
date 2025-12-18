# Player Client Configuration
from pathlib import Path

# Get the client directory (where config.py is located)
CLIENT_DIR = Path(__file__).parent.resolve()

# Server Connection - 改為遠端 IP
SERVER_HOST = 'linux1.cs.nycu.edu.tw'  # 或使用主機名
LOBBY_PORT = 8889

# File Storage
GAMES_DIR = 'games'
PLUGINS_DIR = 'plugins'

# Downloads directory - 使用絕對路徑
DOWNLOADS_DIR = str(CLIENT_DIR / 'downloads')

# UI Settings
THEME = 'dark'
COLOR_THEME = 'blue'

# Network
CHUNK_SIZE = 8192
CONNECT_TIMEOUT = 10
RECONNECT_ATTEMPTS = 3

# Debug
DEBUG = False