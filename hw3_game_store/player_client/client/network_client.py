"""
Network Client for Player
Handles connection to Lobby Server using threading
"""
import socket
import threading
import logging
import queue
from typing import Optional, Callable, Dict
import struct
import json

from protocol import Message, MessageType

logger = logging.getLogger(__name__)


class NetworkClient:
    """Threaded network client for Player"""
    
    def __init__(self, on_message_callback: Callable = None):
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.user_info = None
        
        self.on_message = on_message_callback
        
        # Threading
        self.receive_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Message queues
        self.send_queue = queue.Queue()
        self.response_events = {}  # msg_type -> Event
        self.responses = {}  # msg_type -> response
        
        # Download message queue - for DOWNLOAD_META, DOWNLOAD_CHUNK, DOWNLOAD_COMPLETE
        self.download_queue = queue.Queue()
        self.download_in_progress = False  # Track if download is in progress
        
        self.lock = threading.Lock()
    
    def connect(self, host: str, port: int) -> bool:
        """Connect to server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((host, port))
            self.socket.settimeout(None)
            
            self.connected = True
            self.running = True
            
            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            logger.info(f"Connected to {host}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from server"""
        self.running = False
        self.connected = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        logger.info("Disconnected from server")
    
    def send_message(self, message: Message) -> bool:
        """Send a message to server"""
        if not self.connected:
            logger.warning("Not connected to server")
            return False
        
        try:
            data = message.serialize()
            with self.lock:
                self.socket.sendall(data)
            
            # Track download state
            if message.msg_type == MessageType.DOWNLOAD_REQUEST:
                self.download_in_progress = True
                logger.debug("Download started - set download_in_progress = True")
            
            return True
        except Exception as e:
            logger.error(f"Send error: {e}")
            self.connected = False
            return False
    
    def send_and_wait(self, message: Message, timeout: float = 5.0) -> Optional[Message]:
        """Send message and wait for response"""
        logger.debug(f"→ Sending {message.msg_type.name} and waiting for response (timeout={timeout}s)")
        
        if not self.send_message(message):
            logger.warning(f"✗ Failed to send {message.msg_type.name}")
            return None
        
        # Create event for this response
        event = threading.Event()
        self.response_events[message.msg_type] = event
        logger.debug(f"  Created event for {message.msg_type.name}")
        
        # Wait for response
        logger.debug(f"  Waiting for {message.msg_type.name} response...")
        if event.wait(timeout):
            response = self.responses.pop(message.msg_type, None)
            del self.response_events[message.msg_type]
            logger.debug(f"✓ Received response for {message.msg_type.name}: {response.msg_type.name if response else 'None'}")
            return response
        else:
            # Timeout
            if message.msg_type in self.response_events:
                del self.response_events[message.msg_type]
            logger.warning(f"✗ Request timeout: {message.msg_type.name} (no response in {timeout}s)")
            return None
    
    def _receive_loop(self):
        """Background thread to receive messages"""
        while self.running and self.connected:
            try:
                # Read length header
                header = self._recv_exactly(4)
                if not header:
                    break
                
                length = struct.unpack('>I', header)[0]
                
                # Read message
                data = self._recv_exactly(length)
                if not data:
                    break
                
                message = Message.deserialize(data)
                
                # Handle message
                try:
                    self._handle_received_message(message)
                except Exception as e:
                    # Don't let message handling errors stop the receive loop
                    logger.error(f"Error handling message {message.msg_type.name}: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                
            except struct.error as e:
                # Protocol error - connection might be broken
                if self.running:
                    logger.error(f"Protocol error: {e}")
                break
            except Exception as e:
                # Network error - connection broken
                if self.running:
                    logger.error(f"Receive error: {e}")
                break
        
        self.connected = False
        logger.info("Receive loop stopped")
    
    def _recv_exactly(self, n: int) -> bytes:
        """Receive exactly n bytes"""
        data = b''
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            if not chunk:
                return b''
            data += chunk
        return data
    
    def _handle_received_message(self, message: Message):
        """Handle received message"""
        logger.debug(f"Received: {message.msg_type.name}")
        
        # Check if this is a download-related message
        download_messages = {
            MessageType.DOWNLOAD_META,
            MessageType.DOWNLOAD_CHUNK,
            MessageType.DOWNLOAD_COMPLETE
        }
        
        if message.msg_type in download_messages:
            # Put in download queue for DownloadManager
            self.download_queue.put(message)
            
            # Reset download flag when complete
            if message.msg_type == MessageType.DOWNLOAD_COMPLETE:
                self.download_in_progress = False
                logger.debug("Download complete - set download_in_progress = False")
            
            return
        
        # Special handling for ERROR during download
        # If ERROR is received while download is in progress,
        # put ERROR in download queue so DownloadManager can handle it
        if message.msg_type == MessageType.ERROR and self.download_in_progress:
            logger.debug("ERROR received during download - putting in download_queue")
            self.download_queue.put(message)
            self.download_in_progress = False  # Reset flag
            logger.debug("Download error - set download_in_progress = False")
            return
        
        # Map responses to requests
        response_map = {
            MessageType.AUTH_RESPONSE: MessageType.AUTH_REQUEST,
            MessageType.REGISTER_RESPONSE: MessageType.REGISTER_REQUEST,
            MessageType.GAME_LIST_RESPONSE: MessageType.GAME_LIST_REQUEST,
            MessageType.GAME_DETAIL_RESPONSE: MessageType.GAME_DETAIL_REQUEST,
            MessageType.ROOM_LIST_RESPONSE: MessageType.ROOM_LIST_REQUEST,
            MessageType.ROOM_CREATED: MessageType.CREATE_ROOM,
            MessageType.ROOM_JOINED: MessageType.JOIN_ROOM,
            MessageType.REVIEW_SUBMITTED: MessageType.SUBMIT_REVIEW,
            MessageType.REVIEWS_RESPONSE: MessageType.GET_REVIEWS,
            MessageType.UPDATE_AVAILABLE: MessageType.CHECK_UPDATE,
        }
        
        request_type = response_map.get(message.msg_type)
        logger.debug(f"Mapped {message.msg_type.name} -> {request_type.name if request_type else 'None'}")
        logger.debug(f"Pending events: {[t.name for t in self.response_events.keys()]}")
        
        # Check for specific response first
        if request_type and request_type in self.response_events:
            # This is a response to a pending request
            logger.debug(f"✓ Matched specific response: {message.msg_type.name} -> {request_type.name}")
            self.responses[request_type] = message
            self.response_events[request_type].set()
            logger.debug(f"✓ Event set for {request_type.name}")
            return
        
        # Handle SUCCESS and ERROR as universal responses (fallback)
        if message.msg_type in (MessageType.SUCCESS, MessageType.ERROR):
            # SUCCESS/ERROR can be response to any pending request
            # Find any pending request and respond to it
            for pending_type, event in list(self.response_events.items()):
                if event.is_set():
                    continue  # Already responded
                # Use this SUCCESS/ERROR for the pending request
                self.responses[pending_type] = message
                event.set()
                logger.debug(f"SUCCESS/ERROR matched to pending {pending_type.name}")
                return
        
        # Unsolicited message (notification)
        if self.on_message:
            try:
                self.on_message(message)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")
                import traceback
                logger.debug(traceback.format_exc())
    
    # High-level API methods
    
    def login(self, username: str, password: str) -> tuple[bool, str, str]:
        """Login to server"""
        msg = Message(MessageType.AUTH_REQUEST, {
            'username': username,
            'password': password
        })
        
        response = self.send_and_wait(msg)
        
        if response and response.payload.get('success'):
            self.user_info = {
                'user_id': response.payload['user_id'],
                'username': response.payload['username'],
                'session_token': response.payload.get('session_token')
            }
            return True, "Login successful", response.payload['username']
        else:
            error = response.payload.get('error', 'Unknown error') if response else 'No response'
            return False, error, ""
    
    def register(self, username: str, password: str) -> tuple[bool, str]:
        """Register new account"""
        msg = Message(MessageType.REGISTER_REQUEST, {
            'username': username,
            'password': password
        })
        
        response = self.send_and_wait(msg)
        
        if response and response.payload.get('success'):
            return True, "Registration successful"
        else:
            error = response.payload.get('error', 'Unknown error') if response else 'No response'
            return False, error
    
    def get_game_list(self) -> list:
        """Get list of games (P1)"""
        msg = Message(MessageType.GAME_LIST_REQUEST, {})
        response = self.send_and_wait(msg)
        
        if response:
            return response.payload.get('games', [])
        return []
    
    def get_game_detail(self, game_id: int) -> Optional[dict]:
        """Get game details (P1)"""
        msg = Message(MessageType.GAME_DETAIL_REQUEST, {'game_id': game_id})
        response = self.send_and_wait(msg)
        
        if response:
            return response.payload
        return None
    
    def get_room_list(self) -> list:
        """Get list of rooms (P3)"""
        msg = Message(MessageType.ROOM_LIST_REQUEST, {})
        response = self.send_and_wait(msg)
        
        if response:
            return response.payload.get('rooms', [])
        return []
    
    def create_room(self, game_id: int, room_name: str, max_players: int) -> Optional[dict]:
        """Create a room (P3)"""
        msg = Message(MessageType.CREATE_ROOM, {
            'game_id': game_id,
            'name': room_name,
            'max_players': max_players
        })
        response = self.send_and_wait(msg)
        
        if response and response.payload.get('success'):
            return response.payload
        return None
    
    def join_room(self, room_id: int) -> tuple[bool, str]:
        """Join a room (P3)"""
        logger.debug(f"→ Joining room {room_id}")
        msg = Message(MessageType.JOIN_ROOM, {'room_id': room_id})
        response = self.send_and_wait(msg, timeout=10)
        
        logger.debug(f"← Join room response: {response.msg_type.name if response else 'None'}")
        
        if response:
            # Check for ROOM_JOINED or SUCCESS response
            if response.msg_type == MessageType.ROOM_JOINED or \
               response.msg_type == MessageType.SUCCESS or \
               response.payload.get('success'):
                logger.debug(f"✓ Join room success via {response.msg_type.name}")
                return True, "Joined successfully"
            elif response.msg_type == MessageType.ERROR:
                logger.debug(f"✗ Join room error: {response.payload.get('error')}")
                return False, response.payload.get('error', 'Failed to join')
        
        logger.warning("✗ Join room timeout - no response received")
        return False, 'No response'
    
    def leave_room(self, room_id: int) -> tuple[bool, str]:
        """Leave a room (P3)"""
        msg = Message(MessageType.LEAVE_ROOM, {'room_id': room_id})
        response = self.send_and_wait(msg, timeout=5)
        
        if response:
            # SUCCESS or ERROR response
            if response.msg_type == MessageType.SUCCESS:
                return True, "Left room"
            elif response.msg_type == MessageType.ERROR:
                return False, response.payload.get('error', 'Failed to leave')
        return False, "No response"
    
    def start_game(self, room_id: int) -> tuple[bool, str]:
        """Start game in room (P3 - Host only)"""
        msg = Message(MessageType.START_GAME_REQUEST, {'room_id': room_id})
        response = self.send_and_wait(msg, timeout=10)
        
        if response:
            # SUCCESS or ERROR response  
            if response.msg_type == MessageType.SUCCESS:
                return True, "Game starting"
            elif response.msg_type == MessageType.ERROR:
                error = response.payload.get('error', 'Failed to start')
                return False, error
        return False, "No response"
    
    def submit_review(self, game_id: int, rating: int, comment: str) -> tuple[bool, str]:
        """Submit game review (P4)"""
        msg = Message(MessageType.SUBMIT_REVIEW, {
            'game_id': game_id,
            'rating': rating,
            'comment': comment
        })
        response = self.send_and_wait(msg)
        
        if response and response.payload.get('success'):
            return True, "Review submitted"
        else:
            error = response.payload.get('error', 'Failed') if response else 'No response'
            return False, error
    
    def get_reviews(self, game_id: int) -> list:
        """Get game reviews (P4)"""
        msg = Message(MessageType.GET_REVIEWS, {'game_id': game_id, 'limit': 20})
        response = self.send_and_wait(msg)
        
        if response:
            return response.payload.get('reviews', [])
        return []