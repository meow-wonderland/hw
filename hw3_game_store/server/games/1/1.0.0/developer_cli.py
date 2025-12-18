#!/usr/bin/env python3
"""
Developer Client - CLI for game management
Supports: D1 (Upload), D2 (Update), D3 (Remove)
"""
import socket
import struct
import json
import sys
import hashlib
import zipfile
from pathlib import Path
import getpass

from protocol import Message, MessageType


class DeveloperClient:
    """Developer client for game management"""
    
    def __init__(self, host='localhost', port=8889):
        self.host = host
        self.port = port
        self.sock = None
        self.user = None
    
    def connect(self):
        """Connect to developer server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print(f"✓ Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def send_message(self, msg: Message):
        """Send message"""
        data = msg.serialize()
        self.sock.sendall(data)
    
    def receive_message(self) -> Message:
        """Receive message"""
        header = self._recv_exactly(4)
        length = struct.unpack('>I', header)[0]
        data = self._recv_exactly(length)
        return Message.deserialize(data)
    
    def _recv_exactly(self, n):
        """Receive exactly n bytes"""
        data = b''
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection lost")
            data += chunk
        return data
    
    def login(self):
        """Login as developer"""
        print("\n=== Developer Login ===")
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        
        msg = Message(MessageType.AUTH_REQUEST, {
            'username': username,
            'password': password
        })
        self.send_message(msg)
        
        response = self.receive_message()
        
        if response.payload.get('success'):
            self.user = response.payload
            print(f"✓ Welcome, {username}!")
            return True
        else:
            error = response.payload.get('error', 'Unknown error')
            print(f"✗ Login failed: {error}")
            return False
    
    def register(self):
        """Register new developer"""
        print("\n=== Developer Registration ===")
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        
        if password != confirm:
            print("✗ Passwords don't match")
            return False
        
        msg = Message(MessageType.REGISTER_REQUEST, {
            'username': username,
            'password': password
        })
        self.send_message(msg)
        
        response = self.receive_message()
        
        if response.payload.get('success'):
            print(f"✓ Registration successful! Please login.")
            return True
        else:
            error = response.payload.get('error', 'Unknown error')
            print(f"✗ Registration failed: {error}")
            return False
    
    def my_games(self):
        """List my games"""
        msg = Message(MessageType.MY_GAMES_REQUEST, {})
        self.send_message(msg)
        
        response = self.receive_message()
        games = response.payload.get('games', [])
        
        if not games:
            print("\nYou haven't uploaded any games yet.")
            return games
        
        print(f"\n=== Your Games ({len(games)}) ===")
        for i, game in enumerate(games, 1):
            status_icon = "✓" if game['status'] == 'active' else "✗"
            print(f"{i}. [{status_icon}] {game['name']} (v{game['version']})")
            print(f"   Status: {game['status']} | "
                  f"Downloads: {game['downloads']} | "
                  f"Rating: {game['rating']:.1f}/5.0")
        
        return games
    
    def upload_game(self):
        """D1: Upload new game"""
        print("\n=== Upload New Game (D1) ===")
        
        # Get game info
        name = input("Game name: ").strip()
        if not name:
            print("✗ Game name is required")
            return
        
        description = input("Description: ").strip()
        version = input("Version (default: 1.0.0): ").strip() or "1.0.0"
        
        min_players = input("Minimum players (default: 2): ").strip()
        min_players = int(min_players) if min_players.isdigit() else 2
        
        max_players = input("Maximum players (default: 2): ").strip()
        max_players = int(max_players) if max_players.isdigit() else 2
        
        game_type = input("Game type (cli/gui, default: cli): ").strip().lower() or "cli"
        
        # Get game directory
        game_path = input("Game directory path: ").strip()
        game_path = Path(game_path)
        
        if not game_path.exists():
            print(f"✗ Directory not found: {game_path}")
            return
        
        # Package game
        print("\nPackaging game...")
        zip_path = f"/tmp/{name}_{version}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in game_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(game_path)
                    zf.write(file_path, arcname)
                    print(f"  Added: {arcname}")
        
        # Calculate checksum
        checksum = self._calculate_checksum(zip_path)
        file_size = Path(zip_path).stat().st_size
        
        print(f"\nPackage created: {file_size} bytes")
        print(f"Checksum: {checksum}")
        
        # Send upload start
        msg = Message(MessageType.UPLOAD_START, {
            'name': name,
            'description': description,
            'version': version,
            'min_players': min_players,
            'max_players': max_players,
            'game_type': game_type,
            'file_size': file_size,
            'checksum': checksum
        })
        self.send_message(msg)
        
        response = self.receive_message()
        if not response.payload.get('ready'):
            print(f"✗ Server not ready: {response.payload}")
            return
        
        # Upload file in chunks
        print("\nUploading...")
        with open(zip_path, 'rb') as f:
            offset = 0
            CHUNK_SIZE = 8192
            
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                msg = Message(MessageType.UPLOAD_CHUNK, {
                    'offset': offset,
                    'data': chunk.hex()
                })
                self.send_message(msg)
                
                # Read chunk response
                chunk_response = self.receive_message()
                if chunk_response.msg_type == MessageType.ERROR:
                    print(f"\n✗ Upload failed: {chunk_response.payload.get('error')}")
                    return
                
                offset += len(chunk)
                
                # Progress
                progress = offset / file_size * 100
                print(f"\rProgress: {progress:.1f}% ({offset}/{file_size} bytes)", end='')
        
        print()  # New line
        
        # Send upload complete
        msg = Message(MessageType.UPLOAD_COMPLETE, {})
        self.send_message(msg)
        
        response = self.receive_message()
        
        if response.msg_type == MessageType.UPLOAD_SUCCESS:
            print(f"\n✓ Game '{name}' uploaded successfully!")
            print(f"  Game ID: {response.payload.get('game_id')}")
        elif response.msg_type == MessageType.ERROR:
            error = response.payload.get('error', 'Unknown error')
            print(f"\n✗ Upload failed: {error}")
        else:
            print(f"\n✗ Upload failed: Unexpected response type {response.msg_type.name}")
    
    def update_game(self):
        """D2: Update existing game"""
        print("\n=== Update Game (D2) ===")
        
        # List games first
        games = self.my_games()
        if not games:
            return
        
        choice = input("\nSelect game number to update: ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(games):
            print("✗ Invalid choice")
            return
        
        game = games[int(choice) - 1]
        print(f"\nUpdating: {game['name']} (current version: {game['version']})")
        
        new_version = input("New version: ").strip()
        if not new_version:
            print("✗ Version is required")
            return
        
        changelog = input("Changelog: ").strip()
        
        game_path = input("Game directory path: ").strip()
        game_path = Path(game_path)
        
        if not game_path.exists():
            print(f"✗ Directory not found: {game_path}")
            return
        
        # Package and upload (similar to upload_game)
        print("\nPackaging update...")
        zip_path = f"/tmp/{game['name']}_{new_version}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in game_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(game_path)
                    zf.write(file_path, arcname)
        
        checksum = self._calculate_checksum(zip_path)
        file_size = Path(zip_path).stat().st_size
        
        # Send update request
        msg = Message(MessageType.UPDATE_GAME, {
            'game_id': game['id'],
            'new_version': new_version,
            'changelog': changelog,
            'file_size': file_size,
            'checksum': checksum
        })
        self.send_message(msg)
        
        response = self.receive_message()
        if not response.payload.get('ready'):
            print(f"✗ Server not ready")
            return
        
        # Upload chunks
        print("\nUploading update...")
        with open(zip_path, 'rb') as f:
            offset = 0
            CHUNK_SIZE = 8192
            
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                msg = Message(MessageType.UPLOAD_CHUNK, {
                    'offset': offset,
                    'data': chunk.hex()
                })
                self.send_message(msg)
                
                # Read chunk response
                chunk_response = self.receive_message()
                if chunk_response.msg_type == MessageType.ERROR:
                    print(f"\n✗ Upload failed: {chunk_response.payload.get('error')}")
                    return
                
                offset += len(chunk)
                
                progress = offset / file_size * 100
                print(f"\rProgress: {progress:.1f}%", end='')
        
        print()
        
        msg = Message(MessageType.UPLOAD_COMPLETE, {})
        self.send_message(msg)
        
        response = self.receive_message()
        
        if response.msg_type == MessageType.UPLOAD_SUCCESS or response.payload.get('success'):
            print(f"\n✓ Game updated to version {new_version}!")
        else:
            print(f"\n✗ Update failed: {response.payload.get('error', 'Unknown error')}")
    
    def remove_game(self):
        """D3: Remove (deactivate) game"""
        print("\n=== Remove Game (D3) ===")
        
        games = self.my_games()
        if not games:
            return
        
        choice = input("\nSelect game number to remove: ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(games):
            print("✗ Invalid choice")
            return
        
        game = games[int(choice) - 1]
        
        confirm = input(f"\n⚠️  Remove '{game['name']}'? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Cancelled")
            return
        
        msg = Message(MessageType.REMOVE_GAME, {'game_id': game['id']})
        self.send_message(msg)
        
        response = self.receive_message()
        
        if response.payload.get('success'):
            print(f"\n✓ Game '{game['name']}' removed")
        else:
            error = response.payload.get('error', 'Unknown error')
            print(f"\n✗ Failed to remove game: {error}")
    
    def main_menu(self):
        """Main menu"""
        while True:
            print("\n" + "=" * 50)
            print("Developer Client - Main Menu")
            print("=" * 50)
            print("1. My Games")
            print("2. Upload New Game (D1)")
            print("3. Update Game (D2)")
            print("4. Remove Game (D3)")
            print("5. Logout")
            print("0. Exit")
            
            choice = input("\nChoice: ").strip()
            
            if choice == '1':
                self.my_games()
            elif choice == '2':
                self.upload_game()
            elif choice == '3':
                self.update_game()
            elif choice == '4':
                self.remove_game()
            elif choice == '5':
                return False
            elif choice == '0':
                return True
            else:
                print("Invalid choice")
    
    @staticmethod
    def _calculate_checksum(filepath):
        """Calculate SHA256"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def run(self):
        """Run client"""
        print("=" * 50)
        print("Game Store - Developer Client")
        print("=" * 50)
        
        if not self.connect():
            return
        
        while True:
            print("\n1. Login")
            print("2. Register")
            print("0. Exit")
            
            choice = input("\nChoice: ").strip()
            
            if choice == '1':
                if self.login():
                    if self.main_menu():
                        break
            elif choice == '2':
                self.register()
            elif choice == '0':
                break
        
        if self.sock:
            self.sock.close()
        
        print("\nGoodbye!")


def main():
    import sys
    
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8889
    
    client = DeveloperClient(host, port)
    client.run()


if __name__ == '__main__':
    main()