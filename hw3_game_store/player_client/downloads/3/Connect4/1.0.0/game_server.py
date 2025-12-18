#!/usr/bin/env python3
"""
Connect4 Game Server
Manages a 2-player Connect 4 game
"""
import asyncio
import sys
import argparse
import json


class Connect4Game:
    """Connect 4 game logic"""
    
    def __init__(self):
        self.board = [[' ' for _ in range(7)] for _ in range(6)]
        self.current_player = 0  # 0 or 1
        self.game_over = False
        self.winner = None
    
    def drop_piece(self, col: int, player: int) -> tuple:
        """Drop piece in column, return (row, col) or None if invalid"""
        if col < 0 or col >= 7:
            return None
        
        # Find lowest empty row
        for row in range(5, -1, -1):
            if self.board[row][col] == ' ':
                self.board[row][col] = '●' if player == 0 else '○'
                return (row, col)
        
        return None  # Column full
    
    def check_winner(self, row: int, col: int) -> bool:
        """Check if last move created a win"""
        piece = self.board[row][col]
        
        # Check horizontal
        count = 1
        # Left
        for c in range(col - 1, -1, -1):
            if self.board[row][c] == piece:
                count += 1
            else:
                break
        # Right
        for c in range(col + 1, 7):
            if self.board[row][c] == piece:
                count += 1
            else:
                break
        if count >= 4:
            return True
        
        # Check vertical
        count = 1
        for r in range(row + 1, 6):
            if self.board[r][col] == piece:
                count += 1
            else:
                break
        if count >= 4:
            return True
        
        # Check diagonal /
        count = 1
        r, c = row - 1, col + 1
        while r >= 0 and c < 7:
            if self.board[r][c] == piece:
                count += 1
                r -= 1
                c += 1
            else:
                break
        r, c = row + 1, col - 1
        while r < 6 and c >= 0:
            if self.board[r][c] == piece:
                count += 1
                r += 1
                c -= 1
            else:
                break
        if count >= 4:
            return True
        
        # Check diagonal \
        count = 1
        r, c = row - 1, col - 1
        while r >= 0 and c >= 0:
            if self.board[r][c] == piece:
                count += 1
                r -= 1
                c -= 1
            else:
                break
        r, c = row + 1, col + 1
        while r < 6 and c < 7:
            if self.board[r][c] == piece:
                count += 1
                r += 1
                c += 1
            else:
                break
        if count >= 4:
            return True
        
        return False
    
    def is_full(self) -> bool:
        """Check if board is full"""
        return all(self.board[0][c] != ' ' for c in range(7))
    
    def get_board_state(self) -> list:
        """Get current board state"""
        return [row.copy() for row in self.board]


class GameServer:
    """Async game server"""
    
    def __init__(self, port, players, room_id):
        self.port = port
        self.player_names = players
        self.room_id = room_id
        
        self.game = Connect4Game()
        self.clients = {}  # player_id -> (reader, writer)
        self.player_count = 0
    
    async def start(self):
        """Start server"""
        server = await asyncio.start_server(
            self.handle_client,
            '0.0.0.0',
            self.port
        )
        
        print(f"[Connect4 Server] Started on port {self.port}")
        print(f"[Connect4 Server] Room: {self.room_id}")
        print(f"[Connect4 Server] Players: {', '.join(self.player_names)}")
        
        async with server:
            await server.serve_forever()
    
    async def handle_client(self, reader, writer):
        """Handle client connection"""
        addr = writer.get_extra_info('peername')
        player_id = self.player_count
        self.player_count += 1
        
        if player_id >= 2:
            writer.write(b"FULL\n")
            await writer.drain()
            writer.close()
            return
        
        print(f"[Connect4 Server] Player {player_id} connected: {addr}")
        
        self.clients[player_id] = (reader, writer)
        
        # Send welcome
        await self.send_message(writer, {
            'type': 'welcome',
            'player_id': player_id,
            'player_name': self.player_names[player_id] if player_id < len(self.player_names) else f"Player{player_id}",
            'opponent': self.player_names[1-player_id] if len(self.player_names) > 1-player_id else "Waiting..."
        })
        
        # Wait for all players
        if len(self.clients) == 2:
            await self.broadcast({
                'type': 'start',
                'current_player': self.game.current_player
            })
        
        # Game loop
        try:
            while not self.game.game_over:
                data = await reader.readline()
                if not data:
                    break
                
                try:
                    msg = json.loads(data.decode())
                    await self.handle_message(player_id, msg)
                except:
                    pass
        
        except Exception as e:
            print(f"[Connect4 Server] Error: {e}")
        finally:
            del self.clients[player_id]
            writer.close()
            print(f"[Connect4 Server] Player {player_id} disconnected")
    
    async def handle_message(self, player_id, msg):
        """Handle client message"""
        if msg['type'] == 'move':
            if player_id != self.game.current_player:
                return  # Not your turn
            
            col = msg['column']
            result = self.game.drop_piece(col, player_id)
            
            if result:
                row, col = result
                
                # Broadcast move
                await self.broadcast({
                    'type': 'move',
                    'player': player_id,
                    'row': row,
                    'column': col
                })
                
                # Check win
                if self.game.check_winner(row, col):
                    self.game.game_over = True
                    self.game.winner = player_id
                    await self.broadcast({
                        'type': 'game_over',
                        'winner': player_id
                    })
                elif self.game.is_full():
                    self.game.game_over = True
                    await self.broadcast({
                        'type': 'game_over',
                        'winner': None  # Draw
                    })
                else:
                    # Next turn
                    self.game.current_player = 1 - self.game.current_player
                    await self.broadcast({
                        'type': 'next_turn',
                        'current_player': self.game.current_player
                    })
    
    async def send_message(self, writer, msg):
        """Send JSON message"""
        data = json.dumps(msg).encode() + b'\n'
        writer.write(data)
        await writer.drain()
    
    async def broadcast(self, msg):
        """Broadcast to all clients"""
        for player_id, (reader, writer) in self.clients.items():
            await self.send_message(writer, msg)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--room-id', required=True)
    parser.add_argument('--players', required=True)
    parser.add_argument('--game-name', default='Connect4')
    args = parser.parse_args()
    
    players = args.players.split(',')
    
    server = GameServer(args.port, players, args.room_id)
    await server.start()


if __name__ == '__main__':
    asyncio.run(main())
