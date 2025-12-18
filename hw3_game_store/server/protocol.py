"""
Communication Protocol Definition
Uses Length-Prefix + JSON format for reliable message framing
"""
from enum import IntEnum
import struct
import json
import logging

logger = logging.getLogger(__name__)


class MessageType(IntEnum):
    # Authentication (0x00XX)
    AUTH_REQUEST = 0x0001
    AUTH_RESPONSE = 0x0002
    REGISTER_REQUEST = 0x0003
    REGISTER_RESPONSE = 0x0004
    LOGOUT = 0x0005
    
    # Game Store Browsing (0x01XX)
    GAME_LIST_REQUEST = 0x0101
    GAME_LIST_RESPONSE = 0x0102
    GAME_DETAIL_REQUEST = 0x0103
    GAME_DETAIL_RESPONSE = 0x0104
    SEARCH_GAMES = 0x0105
    
    # Download Management (0x02XX)
    DOWNLOAD_REQUEST = 0x0201
    DOWNLOAD_META = 0x0202
    DOWNLOAD_CHUNK = 0x0203
    DOWNLOAD_COMPLETE = 0x0204
    CHECK_UPDATE = 0x0205
    UPDATE_AVAILABLE = 0x0206
    
    # Room Management (0x03XX)
    CREATE_ROOM = 0x0301
    ROOM_CREATED = 0x0302
    JOIN_ROOM = 0x0303
    ROOM_JOINED = 0x0304
    LEAVE_ROOM = 0x0305
    ROOM_LIST_REQUEST = 0x0306
    ROOM_LIST_RESPONSE = 0x0307
    START_GAME_REQUEST = 0x0308
    GAME_STARTED = 0x0309
    ROOM_UPDATE = 0x030A
    
    # Review System (0x04XX)
    SUBMIT_REVIEW = 0x0401
    REVIEW_SUBMITTED = 0x0402
    GET_REVIEWS = 0x0403
    REVIEWS_RESPONSE = 0x0404
    
    # Developer Operations (0x05XX)
    UPLOAD_START = 0x0501
    UPLOAD_READY = 0x0502
    UPLOAD_CHUNK = 0x0503
    UPLOAD_COMPLETE = 0x0504
    UPLOAD_SUCCESS = 0x0505
    UPDATE_GAME = 0x0506
    UPDATE_SUCCESS = 0x0507
    REMOVE_GAME = 0x0508
    REMOVE_SUCCESS = 0x0509
    MY_GAMES_REQUEST = 0x050A
    MY_GAMES_RESPONSE = 0x050B
    
    # Plugin System (0x06XX)
    PLUGIN_LIST_REQUEST = 0x0601
    PLUGIN_LIST_RESPONSE = 0x0602
    PLUGIN_DOWNLOAD = 0x0603
    PLUGIN_MESSAGE = 0x0604
    
    # General
    ERROR = 0x00FF
    SUCCESS = 0x00FE
    HEARTBEAT = 0x00FD


class Message:
    """Protocol message with length-prefix framing"""
    
    def __init__(self, msg_type: MessageType, payload: dict):
        self.msg_type = msg_type
        self.payload = payload
    
    def serialize(self) -> bytes:
        """Serialize message to bytes with length prefix"""
        try:
            payload_json = json.dumps(self.payload)
            payload_bytes = payload_json.encode('utf-8')
            
            # Format: [Length:4bytes][Type:2bytes][Payload:N bytes]
            length = len(payload_bytes) + 2  # +2 for type field
            header = struct.pack('>IH', length, self.msg_type)
            
            return header + payload_bytes
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            raise
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'Message':
        """Deserialize bytes to Message object"""
        try:
            if len(data) < 2:
                raise ValueError("Data too short")
            
            msg_type = struct.unpack('>H', data[:2])[0]
            payload_data = data[2:]
            
            if payload_data:
                payload = json.loads(payload_data.decode('utf-8'))
            else:
                payload = {}
            
            return cls(MessageType(msg_type), payload)
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            raise
    
    @classmethod
    async def read_from_stream(cls, reader):
        """Read a complete message from asyncio StreamReader"""
        try:
            # Read length header (4 bytes)
            header = await reader.readexactly(4)
            length = struct.unpack('>I', header)[0]
            
            # Read the rest of message
            data = await reader.readexactly(length)
            
            return cls.deserialize(data)
        except Exception as e:
            logger.error(f"Read error: {e}")
            raise
    
    async def write_to_stream(self, writer):
        """Write message to asyncio StreamWriter"""
        try:
            writer.write(self.serialize())
            await writer.drain()
        except Exception as e:
            logger.error(f"Write error: {e}")
            raise
    
    def __repr__(self):
        return f"Message({self.msg_type.name}, {self.payload})"


def create_error_message(error_msg: str, code: int = 500) -> Message:
    """Helper to create error messages"""
    return Message(MessageType.ERROR, {
        'error': error_msg,
        'code': code
    })


def create_success_message(data: dict = None) -> Message:
    """Helper to create success messages"""
    return Message(MessageType.SUCCESS, data or {'success': True})
