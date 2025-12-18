"""
Download Manager
Handles game file downloads with progress tracking (P2)
"""
import os
import hashlib
import logging
import queue
from pathlib import Path
from typing import Callable, Optional
import struct

from protocol import Message, MessageType
import config

logger = logging.getLogger(__name__)


class DownloadManager:
    """Manages game downloads"""
    
    def __init__(self, username, network_client):
        """
        Initialize download manager
        
        Args:
            username: Username for per-player download directory
            network_client: Network client instance
        """
        self.username = username
        self.network = network_client
        
        # Create per-player download directory
        base_downloads = Path(config.DOWNLOADS_DIR)
        self.downloads_dir = base_downloads / str(username)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Download manager initialized for player: {username}")
        logger.info(f"Player downloads directory: {self.downloads_dir}")
        
        # Track active download
        self.current_download = None
    
    def download_game(self, game_id: int, version: str = None,
                     progress_callback: Callable[[int, int], None] = None,
                     complete_callback: Callable[[bool, str], None] = None):
        """
        Download a game (P2)
        
        Args:
            game_id: Game ID to download
            version: Specific version (None for latest)
            progress_callback: Callback(received_bytes, total_bytes)
            complete_callback: Callback(success, message_or_path)
        """
        if not self.network.connected:
            if complete_callback:
                complete_callback(False, "Not connected to server")
            return
        
        # Send download request
        msg = Message(MessageType.DOWNLOAD_REQUEST, {
            'game_id': game_id,
            'version': version
        })
        
        if not self.network.send_message(msg):
            if complete_callback:
                complete_callback(False, "Failed to send request")
            return
        
        # Start receiving download in background thread
        import threading
        thread = threading.Thread(
            target=self._download_worker,
            args=(game_id, progress_callback, complete_callback),
            daemon=True
        )
        thread.start()
    
    def _download_worker(self, game_id: int,
                        progress_callback: Callable = None,
                        complete_callback: Callable = None):
        """Worker thread to receive download"""
        try:
            # Wait for metadata
            meta = self._wait_for_message(MessageType.DOWNLOAD_META, timeout=10)
            if not meta:
                if complete_callback:
                    complete_callback(False, "No metadata received")
                return
            
            # Check if server returned an error
            if meta.msg_type == MessageType.ERROR:
                error_msg = meta.payload.get('error', 'Unknown error')
                logger.error(f"Download failed: {error_msg}")
                if complete_callback:
                    complete_callback(False, error_msg)
                return
            
            game_name = meta.payload['game_name']
            version = meta.payload['version']
            file_size = meta.payload['file_size']
            expected_checksum = meta.payload['checksum']
            
            # Prepare download path
            download_path = self.downloads_dir / f"{game_name}_{version}.zip"
            
            logger.info(f"Downloading {game_name} v{version} ({file_size} bytes)")
            
            # Receive chunks
            received = 0
            with open(download_path, 'wb') as f:
                while received < file_size:
                    chunk_msg = self._wait_for_message(MessageType.DOWNLOAD_CHUNK, timeout=30)
                    if not chunk_msg:
                        raise Exception("Download interrupted")
                    
                    # Check if server returned an error during download
                    if chunk_msg.msg_type == MessageType.ERROR:
                        error_msg = chunk_msg.payload.get('error', 'Download interrupted by server')
                        raise Exception(error_msg)
                    
                    chunk_data = bytes.fromhex(chunk_msg.payload['data'])
                    f.write(chunk_data)
                    received += len(chunk_data)
                    
                    if progress_callback:
                        progress_callback(received, file_size)
            
            # Wait for completion message
            complete_msg = self._wait_for_message(MessageType.DOWNLOAD_COMPLETE, timeout=5)
            
            # Verify checksum
            actual_checksum = self._calculate_checksum(download_path)
            if actual_checksum != expected_checksum:
                download_path.unlink()
                raise Exception("Checksum mismatch - file corrupted")
            
            # Extract game
            extract_dir = self.downloads_dir / game_name / version
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            import zipfile
            import shutil
            
            # Extract to temporary directory first
            temp_extract = self.downloads_dir / f"temp_extract_{game_name}_{version}"
            temp_extract.mkdir(parents=True, exist_ok=True)
            
            try:
                with zipfile.ZipFile(download_path, 'r') as zf:
                    zf.extractall(temp_extract)
                
                # Find the actual game files by looking for game_client.py
                def find_game_files(directory):
                    """Recursively find directory containing game_client.py"""
                    # Check current directory
                    if (directory / "game_client.py").exists():
                        return directory
                    
                    # Check subdirectories
                    for item in directory.iterdir():
                        if item.is_dir():
                            result = find_game_files(item)
                            if result:
                                return result
                    return None
                
                source_dir = find_game_files(temp_extract)
                
                if source_dir and source_dir != temp_extract:
                    # Found game files in a subdirectory - move them
                    logger.info(f"Found game files in: {source_dir.relative_to(temp_extract)}")
                    for item in source_dir.iterdir():
                        dest = extract_dir / item.name
                        if dest.exists():
                            if dest.is_dir():
                                shutil.rmtree(dest)
                            else:
                                dest.unlink()
                        shutil.move(str(item), str(dest))
                elif source_dir == temp_extract:
                    # Files are at root level
                    logger.info("Game files at root level")
                    for item in temp_extract.iterdir():
                        dest = extract_dir / item.name
                        if dest.exists():
                            if dest.is_dir():
                                shutil.rmtree(dest)
                            else:
                                dest.unlink()
                        shutil.move(str(item), str(dest))
                else:
                    # game_client.py not found - extract everything
                    logger.warning("game_client.py not found, extracting all files")
                    for item in temp_extract.iterdir():
                        dest = extract_dir / item.name
                        if dest.exists():
                            if dest.is_dir():
                                shutil.rmtree(dest)
                            else:
                                dest.unlink()
                        shutil.move(str(item), str(dest))
                
            finally:
                # Clean up temp directory
                if temp_extract.exists():
                    shutil.rmtree(temp_extract)
            
            # Delete zip file after extraction
            download_path.unlink()
            
            # Create/update "current" symlink
            current_link = self.downloads_dir / game_name / "current"
            if current_link.exists():
                if current_link.is_symlink():
                    current_link.unlink()
                else:
                    import shutil
                    shutil.rmtree(current_link)
            
            # On Windows, use junction or copy instead of symlink
            if os.name == 'nt':
                import shutil
                shutil.copytree(extract_dir, current_link)
            else:
                current_link.symlink_to(version, target_is_directory=True)
            
            logger.info(f"Download complete: {game_name} v{version}")
            
            if complete_callback:
                complete_callback(True, str(extract_dir))
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            if complete_callback:
                complete_callback(False, str(e))
    
    def _wait_for_message(self, msg_type: MessageType, timeout: float) -> Optional[Message]:
        """Wait for specific message type from download queue"""
        try:
            # Get message from download queue with timeout
            message = self.network.download_queue.get(timeout=timeout)
            
            # Check if it's the expected type or an error
            if message.msg_type == msg_type or message.msg_type == MessageType.ERROR:
                return message
            else:
                logger.warning(f"Expected {msg_type.name}, got {message.msg_type.name}")
                # Put it back if it's not what we expected (shouldn't happen normally)
                self.network.download_queue.put(message)
                return None
                
        except queue.Empty:
            logger.error(f"Timeout waiting for {msg_type.name}")
            return None
        except Exception as e:
            logger.error(f"Error waiting for message: {e}")
            return None
    
    def check_for_updates(self, game_id: int, current_version: str) -> tuple[bool, str]:
        """
        Check if game has updates (P2)
        
        Returns:
            (has_update, latest_version)
        """
        msg = Message(MessageType.CHECK_UPDATE, {
            'game_id': game_id,
            'current_version': current_version
        })
        
        response = self.network.send_and_wait(msg)
        
        if response:
            update_available = response.payload.get('update_available', False)
            latest = response.payload.get('latest_version', current_version)
            return update_available, latest
        
        return False, current_version
    
    def get_installed_games(self) -> list:
        """Get list of locally installed games"""
        installed = []
        
        if not self.downloads_dir.exists():
            return installed
        
        for game_dir in self.downloads_dir.iterdir():
            if game_dir.is_dir() and not game_dir.name.startswith('.'):
                # Check if current version exists
                current = game_dir / 'current'
                if current.exists():
                    # Try to find version
                    version = None
                    for ver_dir in game_dir.iterdir():
                        if ver_dir.is_dir() and ver_dir.name != 'current':
                            version = ver_dir.name
                            break
                    
                    installed.append({
                        'name': game_dir.name,
                        'version': version or 'unknown',
                        'path': str(current)
                    })
        
        return installed
    
    @staticmethod
    def _calculate_checksum(filepath: Path) -> str:
        """Calculate SHA256 checksum"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()