"""
Game Store Server - Main Entry Point
Starts both Lobby Server and Developer Server
"""
import asyncio
import logging
import sys
import socket
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

import config
from lobby_server import LobbyServer
from developer_server import DeveloperServer


def find_available_port(start_port: int, exclude_ports: set = None, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port, excluding certain ports"""
    if exclude_ports is None:
        exclude_ports = set()
    
    for port in range(start_port, start_port + max_attempts):
        # Skip excluded ports
        if port in exclude_ports:
            continue
            
        try:
            # Try to bind to the port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return port
        except OSError:
            # Port is in use, try next one
            continue
    
    # If no port found, raise error
    raise RuntimeError(f"Could not find available port in range {start_port}-{start_port + max_attempts - 1}")


async def main():
    """Start all servers"""
    # Setup logging
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Starting Game Store Server")
    logger.info("=" * 60)
    
    # Create necessary directories
    Path(config.GAMES_DIR).mkdir(exist_ok=True)
    Path(config.PLUGINS_DIR).mkdir(exist_ok=True)
    Path(config.TEMP_DIR).mkdir(exist_ok=True)
    Path('database').mkdir(exist_ok=True)
    
    # Find available ports (make sure they don't conflict)
    try:
        # First find lobby port
        lobby_port = find_available_port(config.LOBBY_PORT)
        
        # Then find developer port, excluding the lobby port
        # If lobby moved to developer's default port, find next available
        if lobby_port == config.DEVELOPER_PORT:
            developer_port = find_available_port(config.DEVELOPER_PORT + 1, exclude_ports={lobby_port})
        else:
            developer_port = find_available_port(config.DEVELOPER_PORT, exclude_ports={lobby_port})
            
    except RuntimeError as e:
        logger.error(f"Failed to find available ports: {e}")
        sys.exit(1)
    
    # Warn if using different ports
    if lobby_port != config.LOBBY_PORT:
        logger.warning(f"Lobby port {config.LOBBY_PORT} is in use, using {lobby_port} instead")
    if developer_port != config.DEVELOPER_PORT:
        logger.warning(f"Developer port {config.DEVELOPER_PORT} is in use, using {developer_port} instead")
    
    # Initialize servers with found ports
    lobby_server = LobbyServer(port=lobby_port)
    developer_server = DeveloperServer(port=developer_port)
    
    logger.info(f"Lobby Server will start on port {lobby_port}")
    logger.info(f"Developer Server will start on port {developer_port}")
    logger.info(f"Game Servers will use ports starting from {config.GAME_SERVER_START_PORT}")
    
    if lobby_port != config.LOBBY_PORT or developer_port != config.DEVELOPER_PORT:
        logger.info("")
        logger.info("⚠️  IMPORTANT: Ports have changed!")
        logger.info(f"   Connect to Lobby Server at: {config.LOBBY_HOST}:{lobby_port}")
        logger.info(f"   Connect to Developer Server at: {config.LOBBY_HOST}:{developer_port}")
        logger.info("")
    
    # Run both servers concurrently
    try:
        await asyncio.gather(
            lobby_server.start(),
            developer_server.start()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
        # Cleanup
        await lobby_server.game_manager.shutdown_all()
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)