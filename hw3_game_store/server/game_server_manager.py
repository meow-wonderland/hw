"""
Game Server Manager
Dynamically spawn and manage game server processes
"""
import asyncio
import sys
import logging
from pathlib import Path
from typing import Dict, Optional
import config

logger = logging.getLogger(__name__)


class GameServerManager:
    """Manages dynamic game server processes"""
    
    def __init__(self):
        self.game_processes: Dict[int, Dict] = {}  # room_id -> process info
        self.next_port = config.GAME_SERVER_START_PORT
        self.port_lock = asyncio.Lock()
    
    async def spawn_game_server(self, room_id: int, game_id: int, game_name: str,
                                players: list, game_version: str = None) -> Optional[int]:
        """
        Spawn a game server process for a room
        
        Args:
            room_id: Room ID
            game_id: Game ID in database
            game_name: Game name/directory
            players: List of player usernames
            game_version: Specific version to run
        
        Returns:
            Port number if successful, None otherwise
        """
        try:
            # Allocate port
            async with self.port_lock:
                port = self.next_port
                self.next_port += 1
            
            # Find game server executable
            game_dir = Path(config.GAMES_DIR) / str(game_id)
            
            if game_version:
                game_path = game_dir / game_version / "game_server.py"
            else:
                game_path = game_dir / "current" / "game_server.py"
            
            if not game_path.exists():
                logger.error(f"Game server not found: {game_path}")
                return None
            
            # Spawn process
            logger.info(f"Spawning game server for room {room_id} on port {port}")
            
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(game_path),
                '--port', str(port),
                '--room-id', str(room_id),
                '--players', ','.join(players),
                '--game-name', game_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=game_path.parent
            )
            
            # Store process info
            self.game_processes[room_id] = {
                'process': proc,
                'port': port,
                'game_id': game_id,
                'players': players,
                'started_at': asyncio.get_event_loop().time()
            }
            
            # Monitor process
            asyncio.create_task(self._monitor_process(room_id, proc))
            
            # Wait a bit to ensure server started
            await asyncio.sleep(0.5)
            
            logger.info(f"Game server started for room {room_id} on port {port}")
            return port
            
        except Exception as e:
            logger.error(f"Failed to spawn game server: {e}")
            return None
    
    async def _monitor_process(self, room_id: int, proc: asyncio.subprocess.Process):
        """Monitor game server process and clean up when it exits"""
        try:
            stdout, stderr = await proc.communicate()
            
            if stdout:
                logger.debug(f"Game server {room_id} stdout: {stdout.decode()}")
            if stderr:
                logger.warning(f"Game server {room_id} stderr: {stderr.decode()}")
            
            logger.info(f"Game server for room {room_id} exited with code {proc.returncode}")
            
        except Exception as e:
            logger.error(f"Error monitoring game server {room_id}: {e}")
        finally:
            # Clean up
            if room_id in self.game_processes:
                del self.game_processes[room_id]
    
    async def stop_game_server(self, room_id: int) -> bool:
        """Stop a game server gracefully"""
        if room_id not in self.game_processes:
            return False
        
        try:
            proc_info = self.game_processes[room_id]
            proc = proc_info['process']
            
            # Try graceful shutdown first
            proc.terminate()
            
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force kill if not responding
                proc.kill()
                await proc.wait()
            
            logger.info(f"Stopped game server for room {room_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping game server {room_id}: {e}")
            return False
    
    def get_game_server_info(self, room_id: int) -> Optional[Dict]:
        """Get info about a running game server"""
        return self.game_processes.get(room_id)
    
    def is_server_running(self, room_id: int) -> bool:
        """Check if game server is running for a room"""
        if room_id not in self.game_processes:
            return False
        
        proc = self.game_processes[room_id]['process']
        return proc.returncode is None
    
    async def shutdown_all(self):
        """Shutdown all game servers"""
        logger.info("Shutting down all game servers")
        
        tasks = []
        for room_id in list(self.game_processes.keys()):
            tasks.append(self.stop_game_server(room_id))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
