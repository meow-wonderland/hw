"""
Developer Server
Handles game upload, update, and removal for developers
"""
import asyncio
import logging
from pathlib import Path
import hashlib
import zipfile
import shutil
from typing import Optional

import config
from protocol import Message, MessageType, create_error_message, create_success_message
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class DeveloperServer:
    """Server for developer operations"""
    
    def __init__(self, host: str = None, port: int = None):
        self.host = host or config.LOBBY_HOST
        self.port = port or config.DEVELOPER_PORT
        self.db = DatabaseManager(config.DB_PATH)
        
        # Track connected developers
        self.clients = {}
        
        # Track ongoing uploads
        self.uploads = {}  # client_id -> upload_info
    
    async def start(self):
        """Start the developer server"""
        server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        
        addr = server.sockets[0].getsockname()
        logger.info(f"Developer Server started on {addr[0]}:{addr[1]}")
        
        async with server:
            await server.serve_forever()
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a developer client connection"""
        addr = writer.get_extra_info('peername')
        client_id = f"{addr[0]}:{addr[1]}"
        
        self.clients[client_id] = {
            'reader': reader,
            'writer': writer,
            'user': None
        }
        
        logger.info(f"Developer connected: {client_id}")
        
        try:
            while True:
                message = await Message.read_from_stream(reader)
                logger.debug(f"Received from {client_id}: {message.msg_type.name}")
                
                response = await self.process_message(client_id, message)
                
                if response:
                    await response.write_to_stream(writer)
                    
        except asyncio.IncompleteReadError:
            logger.info(f"Developer {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error handling developer {client_id}: {e}", exc_info=True)
        finally:
            if client_id in self.clients:
                del self.clients[client_id]
            writer.close()
            await writer.wait_closed()
    
    async def process_message(self, client_id: str, msg: Message):
        """Route message to handler"""
        handlers = {
            MessageType.AUTH_REQUEST: self.handle_auth,
            MessageType.REGISTER_REQUEST: self.handle_register,
            MessageType.MY_GAMES_REQUEST: self.handle_my_games,
            MessageType.UPLOAD_START: self.handle_upload_start,
            MessageType.UPLOAD_CHUNK: self.handle_upload_chunk,
            MessageType.UPLOAD_COMPLETE: self.handle_upload_complete,
            MessageType.UPDATE_GAME: self.handle_update_game,
            MessageType.REMOVE_GAME: self.handle_remove_game,
        }
        
        handler = handlers.get(msg.msg_type)
        if handler:
            return await handler(client_id, msg.payload)
        
        return create_error_message(f"Unknown message type: {msg.msg_type.name}")
    
    async def handle_auth(self, client_id: str, payload: dict) -> Message:
        """Authenticate developer"""
        username = payload.get('username')
        password = payload.get('password')
        
        if not username or not password:
            return create_error_message("Username and password required")
        
        # 使用 authenticate_developer
        developer = self.db.authenticate_developer(username, password)
        
        if not developer:
            return Message(MessageType.AUTH_RESPONSE, {
                'success': False,
                'error': 'Invalid credentials'
            })
        
        # 用 developer 而不是 user
        self.clients[client_id]['user'] = developer
        
        logger.info(f"Developer {username} authenticated")
        
        return Message(MessageType.AUTH_RESPONSE, {
            'success': True,
            'user_id': developer['id'],
            'username': developer['username']
        })
    
    async def handle_register(self, client_id: str, payload: dict) -> Message:
        """Register new developer"""
        username = payload.get('username')
        password = payload.get('password')
        email = payload.get('email', '')
        
        if not username or not password:
            return create_error_message("Username and password required")
        
        # 使用 create_developer
        developer_id = self.db.create_developer(username, password, email)
        
        if not developer_id:
            return Message(MessageType.REGISTER_RESPONSE, {
                'success': False,
                'error': 'Username already exists'
            })
        
        logger.info(f"New developer registered: {username}")
        
        return Message(MessageType.REGISTER_RESPONSE, {
            'success': True,
            'user_id': developer_id
        })
    
    async def handle_my_games(self, client_id: str, payload: dict) -> Message:
        """Get developer's games"""
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        games = self.db.get_games_by_developer(user['id'])
        
        game_list = [{
            'id': g['id'],
            'name': g['name'],
            'description': g['description'],
            'version': g['current_version'],
            'status': g['status'],
            'downloads': g['download_count'],
            'rating': round(g['average_rating'], 1)
        } for g in games]
        
        return Message(MessageType.MY_GAMES_RESPONSE, {
            'games': game_list
        })
    
    async def handle_upload_start(self, client_id: str, payload: dict) -> Message:
        """D1: Start game upload"""
        try:
            user = self.clients[client_id]['user']
            if not user:
                return create_error_message("Not authenticated")
            
            # Extract game info
            name = payload.get('name')
            description = payload.get('description', '')
            version = payload.get('version', '1.0.0')
            min_players = payload.get('min_players', 2)
            max_players = payload.get('max_players', 2)
            game_type = payload.get('game_type', 'cli')
            file_size = payload.get('file_size')
            checksum = payload.get('checksum')
            
            logger.info(f"Upload start request from {user['username']}: name={name}, size={file_size}")
            
            if not name or not file_size or not checksum:
                return create_error_message("Missing required fields")
            
            # Check if game already exists
            existing = self.db.fetchone("SELECT id FROM games WHERE name = ?", (name,))
            if existing:
                logger.warning(f"Game '{name}' already exists")
                return create_error_message("Game name already exists")
            
            # Create temp upload directory
            temp_dir = Path(config.TEMP_DIR) / client_id
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / f"{name}.zip"
            
            logger.info(f"Creating temp file: {temp_file}")
            
            # Initialize upload tracking
            self.uploads[client_id] = {
                'mode': 'new',
                'name': name,
                'description': description,
                'version': version,
                'min_players': min_players,
                'max_players': max_players,
                'game_type': game_type,
                'file_size': file_size,
                'checksum': checksum,
                'temp_file': temp_file,
                'received_bytes': 0,
                'file_handle': open(temp_file, 'wb')
            }
            
            logger.info(f"Upload started: {name} by {user['username']}")
            
            return Message(MessageType.UPLOAD_READY, {
                'ready': True,
                'expected_size': file_size
            })
            
        except Exception as e:
            logger.error(f"Upload start error: {e}", exc_info=True)
            return create_error_message(f"Upload start failed: {str(e)}")
    
    async def handle_upload_chunk(self, client_id: str, payload: dict) -> Message:
        """D1: Receive upload chunk"""
        if client_id not in self.uploads:
            return create_error_message("No upload in progress")
        
        upload = self.uploads[client_id]
        
        data_hex = payload.get('data')
        if not data_hex:
            return create_error_message("No data in chunk")
        
        data = bytes.fromhex(data_hex)
        
        # Write chunk
        upload['file_handle'].write(data)
        upload['received_bytes'] += len(data)
        
        # Progress feedback (optional)
        progress = upload['received_bytes'] / upload['file_size'] * 100
        
        return create_success_message({
            'received': upload['received_bytes'],
            'progress': round(progress, 1)
        })
    
    async def handle_upload_complete(self, client_id: str, payload: dict) -> Message:
        """D1: Finalize upload"""
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        if client_id not in self.uploads:
            return create_error_message("No upload in progress")
        
        upload = self.uploads[client_id]
        
        try:
            upload['file_handle'].close()
            
            # Verify checksum
            received_checksum = self._calculate_checksum(upload['temp_file'])
            if received_checksum != upload['checksum']:
                upload['temp_file'].unlink()
                del self.uploads[client_id]
                return create_error_message("Checksum mismatch - file corrupted")
            
            # Check if this is an update or new upload
            mode = upload.get('mode', 'new')
            
            if mode == 'update':
                # For update, use existing game_id
                game_id = upload['game_id']
                game_name = upload['game_name']
                
                # Verify game still exists and user owns it
                game = self.db.get_game(game_id)
                if not game or game['developer_id'] != user['id']:
                    upload['temp_file'].unlink()
                    del self.uploads[client_id]
                    return create_error_message("Game not found or not owned by you")
            else:
                # For new upload, create game entry
                game_id = self.db.create_game(
                    name=upload['name'],
                    description=upload['description'],
                    developer_id=user['id'],
                    version=upload['version'],
                    min_players=upload['min_players'],
                    max_players=upload['max_players'],
                    game_type=upload['game_type']
                )
                
                if not game_id:
                    upload['temp_file'].unlink()
                    del self.uploads[client_id]
                    return create_error_message("Failed to create game entry")
                
                game_name = upload['name']
            
            # Move file to permanent storage
            game_dir = Path(config.GAMES_DIR) / str(game_id) / upload['version']
            game_dir.mkdir(parents=True, exist_ok=True)
            
            final_path = game_dir / "game_package.zip"
            shutil.move(str(upload['temp_file']), str(final_path))
            
            # Extract the package with smart extraction
            extract_dir = game_dir
            
            # Extract to temporary directory first
            temp_extract = game_dir.parent / f"temp_extract_{game_id}_{upload['version']}"
            temp_extract.mkdir(parents=True, exist_ok=True)
            
            try:
                with zipfile.ZipFile(final_path, 'r') as zf:
                    zf.extractall(temp_extract)
                
                # Find the actual game files by looking for game_server.py
                def find_game_files(directory):
                    """Recursively find directory containing game_server.py"""
                    # Check current directory
                    if (directory / "game_server.py").exists():
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
                    # game_server.py not found - extract everything
                    logger.warning("game_server.py not found, extracting all files")
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
            
            # Keep zip file for downloads - DO NOT DELETE
            # The zip file is needed when players download the game
            
            # Create symlink to current version
            current_link = Path(config.GAMES_DIR) / str(game_id) / "current"
            if current_link.exists():
                if current_link.is_symlink():
                    current_link.unlink()
                else:
                    shutil.rmtree(current_link)
            current_link.symlink_to(upload['version'], target_is_directory=True)
            
            # Add version entry
            changelog = upload.get('changelog', 'Initial release' if mode == 'new' else 'Update')
            self.db.add_game_version(
                game_id=game_id,
                version=upload['version'],
                changelog=changelog,
                file_path=str(final_path),
                file_size=upload['file_size'],
                checksum=upload['checksum']
            )
            
            # Cleanup
            del self.uploads[client_id]
            
            if mode == 'update':
                logger.info(f"Game {game_name} updated to v{upload['version']} by {user['username']}")
                return Message(MessageType.UPLOAD_SUCCESS, {
                    'success': True,
                    'game_id': game_id,
                    'message': f"Game '{game_name}' updated to version {upload['version']}!"
                })
            else:
                logger.info(f"Game {game_name} uploaded successfully by {user['username']}")
                return Message(MessageType.UPLOAD_SUCCESS, {
                    'success': True,
                    'game_id': game_id,
                    'message': f"Game '{game_name}' uploaded successfully!"
                })
            
        except Exception as e:
            logger.error(f"Upload complete error: {e}", exc_info=True)
            if client_id in self.uploads:
                del self.uploads[client_id]
            return create_error_message(f"Upload failed: {str(e)}")
    
    async def handle_update_game(self, client_id: str, payload: dict) -> Message:
        """D2: Update game version"""
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        game_id = payload.get('game_id')
        new_version = payload.get('new_version')
        changelog = payload.get('changelog', '')
        
        # Verify ownership
        game = self.db.get_game(game_id)
        if not game or game['developer_id'] != user['id']:
            return create_error_message("Game not found or not owned by you")
        
        # Similar upload process as UPLOAD_START
        # For simplicity, we'll use the same upload mechanism
        file_size = payload.get('file_size')
        checksum = payload.get('checksum')
        
        if not file_size or not checksum:
            return create_error_message("File info required")
        
        # Setup upload for update
        temp_dir = Path(config.TEMP_DIR) / client_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / f"update_{game_id}_{new_version}.zip"
        
        self.uploads[client_id] = {
            'mode': 'update',
            'game_id': game_id,
            'game_name': game['name'],
            'version': new_version,
            'changelog': changelog,
            'file_size': file_size,
            'checksum': checksum,
            'temp_file': temp_file,
            'received_bytes': 0,
            'file_handle': open(temp_file, 'wb')
        }
        
        logger.info(f"Update started for game {game['name']} to version {new_version}")
        
        return Message(MessageType.UPLOAD_READY, {
            'ready': True,
            'expected_size': file_size
        })
    
    async def handle_remove_game(self, client_id: str, payload: dict) -> Message:
        """D3: Remove (deactivate) game"""
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        game_id = payload.get('game_id')
        
        game = self.db.get_game(game_id)
        if not game or game['developer_id'] != user['id']:
            return create_error_message("Game not found or not owned by you")
        
        # Set status to inactive
        if self.db.update_game_status(game_id, 'inactive'):
            logger.info(f"Game {game['name']} removed by {user['username']}")
            return Message(MessageType.REMOVE_SUCCESS, {
                'success': True,
                'message': f"Game '{game['name']}' has been removed"
            })
        else:
            return create_error_message("Failed to remove game")
    
    @staticmethod
    def _calculate_checksum(filepath: Path) -> str:
        """Calculate SHA256 checksum of file"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


async def main():
    """Main entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = DeveloperServer()
    await server.start()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Developer server shutting down...")