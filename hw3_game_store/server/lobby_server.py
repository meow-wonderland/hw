"""
Lobby Server
Handles player connections, game browsing, downloads, and room management
"""
import asyncio
import logging
from pathlib import Path
import hashlib
from typing import Optional

import config
from protocol import Message, MessageType, create_error_message, create_success_message
from database.db_manager import DatabaseManager
from game_server_manager import GameServerManager

logger = logging.getLogger(__name__)


class LobbyServer:
    """Main lobby server for players"""
    
    def __init__(self, host: str = None, port: int = None):
        self.host = host or config.LOBBY_HOST
        self.port = port or config.LOBBY_PORT
        self.db = DatabaseManager(config.DB_PATH)
        self.game_manager = GameServerManager()
        
        # Track connected clients: client_id -> (reader, writer, user_info)
        self.clients = {}
        
        # Track active rooms
        self.active_rooms = {}  # room_id -> room_info
    
    async def start(self):
        """Start the lobby server"""
        server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        
        addr = server.sockets[0].getsockname()
        logger.info(f"Lobby Server started on {addr[0]}:{addr[1]}")
        
        # Start background task to clean expired rooms
        asyncio.create_task(self.cleanup_expired_rooms())
        
        async with server:
            await server.serve_forever()
    
    async def cleanup_expired_rooms(self):
        """Background task to close expired rooms (every minute)"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                # Close rooms that have been waiting for more than 10 minutes
                self.db.execute(
                    """UPDATE rooms 
                    SET status = 'closed' 
                    WHERE status = 'waiting' 
                    AND datetime(created_at, '+10 minutes') < datetime('now')"""
                )
                
                logger.debug("Expired rooms cleanup completed")
            except Exception as e:
                logger.error(f"Error cleaning expired rooms: {e}")
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a client connection"""
        addr = writer.get_extra_info('peername')
        client_id = f"{addr[0]}:{addr[1]}"
        
        self.clients[client_id] = {
            'reader': reader,
            'writer': writer,
            'user': None,
            'addr': addr
        }
        
        logger.info(f"Client connected: {client_id}")
        
        try:
            while True:
                # Read message
                message = await Message.read_from_stream(reader)
                logger.debug(f"Received from {client_id}: {message.msg_type.name}")
                
                # Process message
                response = await self.process_message(client_id, message)
                
                # Send response
                if response:
                    await response.write_to_stream(writer)
                    
        except asyncio.IncompleteReadError:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}", exc_info=True)
        finally:
            await self.cleanup_client(client_id)
            writer.close()
            await writer.wait_closed()
    
    async def process_message(self, client_id: str, msg: Message) -> Optional[Message]:
        """Route message to appropriate handler"""
        handlers = {
            MessageType.AUTH_REQUEST: self.handle_auth,
            MessageType.REGISTER_REQUEST: self.handle_register,
            MessageType.GAME_LIST_REQUEST: self.handle_game_list,
            MessageType.GAME_DETAIL_REQUEST: self.handle_game_detail,
            MessageType.DOWNLOAD_REQUEST: self.handle_download_request,
            MessageType.ROOM_LIST_REQUEST: self.handle_room_list,
            MessageType.CREATE_ROOM: self.handle_create_room,
            MessageType.JOIN_ROOM: self.handle_join_room,
            MessageType.LEAVE_ROOM: self.handle_leave_room,
            MessageType.START_GAME_REQUEST: self.handle_start_game,
            MessageType.SUBMIT_REVIEW: self.handle_submit_review,
            MessageType.GET_REVIEWS: self.handle_get_reviews,
            MessageType.CHECK_UPDATE: self.handle_check_update,
        }
        
        handler = handlers.get(msg.msg_type)
        if handler:
            return await handler(client_id, msg.payload)
        
        return create_error_message(f"Unknown message type: {msg.msg_type.name}")
    
    async def handle_auth(self, client_id: str, payload: dict) -> Message:
        """Handle authentication"""
        username = payload.get('username')
        password = payload.get('password')
        
        if not username or not password:
            return create_error_message("Username and password required")
        
        # 改這裡：使用 authenticate_player
        player = self.db.authenticate_player(username, password)
        
        if not player:
            return Message(MessageType.AUTH_RESPONSE, {
                'success': False,
                'error': 'Invalid credentials'
            })
        
        # 移除 user_type 檢查（已經是 player 了）
        
        # Store player info（改用 player）
        self.clients[client_id]['user'] = player
        
        # 改這裡：使用 create_player_session
        session_token = self.db.create_player_session(player['id'])
        
        logger.info(f"Player {username} authenticated on {client_id}")
        
        return Message(MessageType.AUTH_RESPONSE, {
            'success': True,
            'user_id': player['id'],
            'username': player['username'],
            'session_token': session_token
        })
    
    async def handle_register(self, client_id: str, payload: dict) -> Message:
        """Handle user registration"""
        username = payload.get('username')
        password = payload.get('password')
        email = payload.get('email', '')  # 添加 email
        
        if not username or not password:
            return create_error_message("Username and password required")
        
        # 改這裡：使用 create_player
        player_id = self.db.create_player(username, password, email)
        
        if not player_id:
            return Message(MessageType.REGISTER_RESPONSE, {
                'success': False,
                'error': 'Username already exists'
            })
        
        logger.info(f"New player registered: {username}")
        
        return Message(MessageType.REGISTER_RESPONSE, {
            'success': True,
            'user_id': player_id,
            'username': username
        })
    
    async def handle_game_list(self, client_id: str, payload: dict) -> Message:
        """P1: Get list of available games"""
        games = self.db.get_active_games()
        
        game_list = []
        for game in games:
            game_list.append({
                'id': game['id'],
                'name': game['name'],
                'description': game['description'],
                'version': game['current_version'],
                'min_players': game['min_players'],
                'max_players': game['max_players'],
                'type': game['game_type'],
                'rating': round(game['average_rating'], 1),
                'rating_count': game['rating_count'],
                'downloads': game['download_count']
            })
        
        return Message(MessageType.GAME_LIST_RESPONSE, {
            'games': game_list
        })
    
    async def handle_game_detail(self, client_id: str, payload: dict) -> Message:
        """P1: Get detailed game information"""
        game_id = payload.get('game_id')
        
        if not game_id:
            return create_error_message("Game ID required")
        
        game = self.db.get_game(game_id)
        if not game:
            return create_error_message("Game not found")
        
        # Get reviews
        reviews = self.db.get_game_reviews(game_id, limit=10)
        
        return Message(MessageType.GAME_DETAIL_RESPONSE, {
            'game': {
                'id': game['id'],
                'name': game['name'],
                'description': game['description'],
                'version': game['current_version'],
                'min_players': game['min_players'],
                'max_players': game['max_players'],
                'type': game['game_type'],
                'rating': round(game['average_rating'], 1),
                'rating_count': game['rating_count'],
                'downloads': game['download_count'],
                'created_at': game['created_at']
            },
            'reviews': reviews
        })
    
    async def handle_download_request(self, client_id: str, payload: dict) -> Message:
        """P2: Handle game download request"""
        game_id = payload.get('game_id')
        version = payload.get('version')  # Can be None for latest
        
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        game = self.db.get_game(game_id)
        if not game or game['status'] != 'active':
            return create_error_message("Game not available")
        
        # Get version info
        if version:
            version_info = self.db.get_game_version(game_id, version)
        else:
            version_info = self.db.get_latest_version(game_id)
            version = version_info['version'] if version_info else None
        
        if not version_info:
            return create_error_message("Version not found")
        
        file_path = Path(version_info['file_path'])
        if not file_path.exists():
            return create_error_message("Game file not found on server")
        
        # Send metadata first
        writer = self.clients[client_id]['writer']
        
        meta_msg = Message(MessageType.DOWNLOAD_META, {
            'game_id': game_id,
            'game_name': game['name'],
            'version': version,
            'file_size': version_info['file_size'],
            'checksum': version_info['checksum']
        })
        await meta_msg.write_to_stream(writer)
        
        # Send file in chunks
        try:
            with open(file_path, 'rb') as f:
                total_sent = 0
                while True:
                    chunk = f.read(config.CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    chunk_msg = Message(MessageType.DOWNLOAD_CHUNK, {
                        'data': chunk.hex(),
                        'offset': total_sent
                    })
                    await chunk_msg.write_to_stream(writer)
                    total_sent += len(chunk)
            
            # Record download
            self.db.record_download(game_id, user['id'], version)
            
            logger.info(f"User {user['username']} downloaded {game['name']} v{version}")
            
            return Message(MessageType.DOWNLOAD_COMPLETE, {
                'success': True,
                'bytes_sent': total_sent
            })
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            return create_error_message(f"Download failed: {str(e)}")
    
    async def handle_check_update(self, client_id: str, payload: dict) -> Message:
        """P2: Check if update available"""
        game_id = payload.get('game_id')
        current_version = payload.get('current_version')
        
        game = self.db.get_game(game_id)
        if not game:
            return create_error_message("Game not found")
        
        latest = game['current_version']
        update_available = latest != current_version
        
        return Message(MessageType.UPDATE_AVAILABLE, {
            'update_available': update_available,
            'current_version': current_version,
            'latest_version': latest
        })
    
    async def handle_room_list(self, client_id: str, payload: dict) -> Message:
        """P3: Get list of active rooms"""
        rooms = self.db.get_active_rooms()
        
        room_list = []
        for room in rooms:
            room_list.append({
                'id': room['id'],
                'name': room['name'],
                'room_code': room['room_code'],
                'game_id': room['game_id'],
                'game_name': room['game_name'],
                'host_name': room['host_name'],
                'current_players': room['current_players'],
                'max_players': room['max_players'],
                'status': room['status']
            })
        
        return Message(MessageType.ROOM_LIST_RESPONSE, {
            'rooms': room_list
        })
    
    async def handle_create_room(self, client_id: str, payload: dict) -> Message:
        """P3: Create a game room"""
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        game_id = payload.get('game_id')
        room_name = payload.get('name', f"{user['username']}'s Room")
        max_players = payload.get('max_players', 4)
        
        game = self.db.get_game(game_id)
        if not game or game['status'] != 'active':
            return create_error_message("Game not available")
        
        room_id = self.db.create_room(game_id, user['id'], room_name, max_players)
        
        if not room_id:
            return create_error_message("Failed to create room")
        
        room = self.db.get_room(room_id)
        
        logger.info(f"Room {room_id} created by {user['username']} for game {game['name']}")
        
        return Message(MessageType.ROOM_CREATED, {
            'success': True,
            'room_id': room_id,
            'room_code': room['room_code'],
            'room_name': room_name
        })
    
    async def handle_join_room(self, client_id: str, payload: dict) -> Message:
        """P3: Join a game room"""
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        room_id = payload.get('room_id')
        
        room = self.db.get_room(room_id)
        if not room:
            return create_error_message("Room not found")
        
        if room['status'] != 'waiting':
            return create_error_message("Room is not accepting players")
        
        if room['current_players'] >= room['max_players']:
            return create_error_message("Room is full")
        
        if not self.db.join_room(room_id, user['id']):
            return create_error_message("Already in room or failed to join")
        
        logger.info(f"User {user['username']} joined room {room_id}")
        
        # Create response first (don't wait for broadcast)
        response = Message(MessageType.ROOM_JOINED, {
            'success': True,
            'room_id': room_id
        })
        
        # Broadcast room update asynchronously (non-blocking)
        asyncio.create_task(self.broadcast_room_update(room_id))
        
        # Return response immediately
        return response
    
    async def handle_leave_room(self, client_id: str, payload: dict) -> Message:
        """P3: Leave a room"""
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        room_id = payload.get('room_id')
        
        # Check if this is the host
        room = self.db.get_room(room_id)
        if room and room['host_id'] == user['id']:
            # Host is leaving - close the room
            self.db.update_room_status(room_id, 'closed')
            logger.info(f"Host {user['username']} left room {room_id} - room closed")
        else:
            # Regular player leaving
            self.db.leave_room(room_id, user['id'])
            logger.info(f"User {user['username']} left room {room_id}")
        
        await self.broadcast_room_update(room_id)
        
        return create_success_message({'left': True})
    
    async def handle_start_game(self, client_id: str, payload: dict) -> Message:
        """P3: Start game (spawn game server)"""
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        room_id = payload.get('room_id')
        
        room = self.db.get_room(room_id)
        if not room:
            return create_error_message("Room not found")
        
        if room['host_id'] != user['id']:
            return create_error_message("Only host can start game")
        
        # Get game info
        game = self.db.get_game(room['game_id'])
        if not game:
            return create_error_message("Game not found")
        
        # Get players
        players_data = self.db.get_room_players(room_id)
        players = [p['username'] for p in players_data]
        
        # Spawn game server
        game_port = await self.game_manager.spawn_game_server(
            room_id=room_id,
            game_id=game['id'],
            game_name=game['name'],
            players=players,
            game_version=game['current_version']
        )
        
        if not game_port:
            return create_error_message("Failed to start game server")
        
        # Update room status
        self.db.update_room_status(room_id, 'playing', game_port)
        
        # Notify all players
        for player_data in players_data:
            player_client = self._find_client_by_user_id(player_data['id'])
            if player_client:
                writer = self.clients[player_client]['writer']
                notify = Message(MessageType.GAME_STARTED, {
                    'room_id': room_id,
                    'game_port': game_port,
                    'game_name': game['name']
                })
                await notify.write_to_stream(writer)
        
        logger.info(f"Game started for room {room_id} on port {game_port}")
        
        return create_success_message({
            'game_port': game_port,
            'room_id': room_id
        })
    
    async def handle_submit_review(self, client_id: str, payload: dict) -> Message:
        """P4: Submit game review"""
        user = self.clients[client_id]['user']
        if not user:
            return create_error_message("Not authenticated")
        
        game_id = payload.get('game_id')
        rating = payload.get('rating')
        comment = payload.get('comment', '')
        
        if not game_id or rating is None:
            return create_error_message("Game ID and rating required")
        
        if not 1 <= rating <= 5:
            return create_error_message("Rating must be between 1 and 5")
        
        if self.db.add_review(game_id, user['id'], rating, comment):
            logger.info(f"User {user['username']} reviewed game {game_id}: {rating} stars")
            return Message(MessageType.REVIEW_SUBMITTED, {'success': True})
        else:
            return create_error_message("Failed to submit review")
    
    async def handle_get_reviews(self, client_id: str, payload: dict) -> Message:
        """P4: Get game reviews"""
        game_id = payload.get('game_id')
        limit = payload.get('limit', 20)
        
        reviews = self.db.get_game_reviews(game_id, limit)
        
        return Message(MessageType.REVIEWS_RESPONSE, {
            'reviews': reviews
        })
    
    async def broadcast_room_update(self, room_id: int):
        """Broadcast room update to all players in the room"""
        room = self.db.get_room(room_id)
        players = self.db.get_room_players(room_id)
        
        update_msg = Message(MessageType.ROOM_UPDATE, {
            'room_id': room_id,
            'current_players': room['current_players'],
            'players': [p['username'] for p in players]
        })
        
        for player in players:
            client = self._find_client_by_user_id(player['id'])
            if client:
                writer = self.clients[client]['writer']
                try:
                    await update_msg.write_to_stream(writer)
                except:
                    pass
    
    def _find_client_by_user_id(self, user_id: int) -> Optional[str]:
        """Find client_id by user_id"""
        for client_id, info in self.clients.items():
            if info['user'] and info['user']['id'] == user_id:
                return client_id
        return None
    
    async def cleanup_client(self, client_id: str):
        """Clean up when client disconnects"""
        if client_id in self.clients:
            user = self.clients[client_id]['user']
            if user:
                logger.info(f"User {user['username']} disconnected")
            del self.clients[client_id]


async def main():
    """Main entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create necessary directories
    Path(config.GAMES_DIR).mkdir(exist_ok=True)
    Path(config.PLUGINS_DIR).mkdir(exist_ok=True)
    Path(config.TEMP_DIR).mkdir(exist_ok=True)
    Path('logs').mkdir(exist_ok=True)
    
    server = LobbyServer()
    await server.start()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutting down...")