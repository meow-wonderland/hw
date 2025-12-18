#!/usr/bin/env python3
"""
Tic Tac Toe Battle - Game Server
A classic 2-player tic-tac-toe game
"""
import asyncio
import json
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TicTacToeServer:
    def __init__(self, port, room_id, players, game_name):
        self.port = port
        self.room_id = room_id
        self.players = players
        self.game_name = game_name
        
        self.clients = {}  # username -> (reader, writer)
        self.scores = {players[0]: 0, players[1]: 0}
        self.current_game = 0
        self.max_games = 3
        
        # Game state
        self.board = [' '] * 9  # 3x3 board as list
        self.current_player = 0  # 0 or 1
        self.symbols = {players[0]: 'X', players[1]: 'O'}
        self.game_active = False
        
        logger.info(f"Game server initialized: {game_name} (Room {room_id})")
        logger.info(f"Players: {players[0]} (X) vs {players[1]} (O)")
    
    async def start(self):
        """Start the game server"""
        server = await asyncio.start_server(
            self.handle_client,
            '0.0.0.0',
            self.port
        )
        
        logger.info(f"⭕ Tic Tac Toe server running on port {self.port}")
        
        async with server:
            await server.serve_forever()
    
    async def handle_client(self, reader, writer):
        """Handle a client connection"""
        addr = writer.get_extra_info('peername')
        logger.info(f"Client connected from {addr}")
        
        try:
            # Wait for player identification
            data = await reader.read(1024)
            message = json.loads(data.decode())
            
            if message['type'] == 'join':
                username = message['username']
                
                if username not in self.players:
                    await self.send_message(writer, {
                        'type': 'error',
                        'message': 'Player not in this game'
                    })
                    writer.close()
                    await writer.wait_closed()
                    return
                
                self.clients[username] = (reader, writer)
                logger.info(f"Player {username} joined")
                
                # Send welcome
                await self.send_message(writer, {
                    'type': 'welcome',
                    'message': f'Welcome to Tic Tac Toe, {username}!',
                    'symbol': self.symbols[username],
                    'players': self.players,
                    'max_games': self.max_games
                })
                
                # Check if both players connected
                if len(self.clients) == 2:
                    logger.info("Both players connected, starting game!")
                    await self.broadcast({
                        'type': 'game_start',
                        'message': 'Both players connected! Game starting...'
                    })
                    await asyncio.sleep(2)
                    await self.start_game()
                else:
                    await self.broadcast({
                        'type': 'waiting',
                        'message': f'Waiting for opponent... ({len(self.clients)}/2)'
                    })
                
                # Handle player messages
                await self.handle_player_messages(username, reader, writer)
        
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def handle_player_messages(self, username, reader, writer):
        """Handle messages from a player"""
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                
                message = json.loads(data.decode())
                msg_type = message['type']
                
                if msg_type == 'move':
                    position = message['position']
                    await self.handle_move(username, position)
        
        except Exception as e:
            logger.error(f"Error in player {username} messages: {e}")
        finally:
            if username in self.clients:
                del self.clients[username]
            logger.info(f"Player {username} disconnected")
    
    async def start_game(self):
        """Start a new game"""
        self.current_game += 1
        self.board = [' '] * 9
        self.current_player = 0
        self.game_active = True
        
        logger.info(f"Game {self.current_game} started")
        
        await self.broadcast({
            'type': 'new_game',
            'game': self.current_game,
            'max_games': self.max_games,
            'scores': self.scores,
            'board': self.board
        })
        
        await asyncio.sleep(1)
        await self.next_turn()
    
    async def next_turn(self):
        """Start next player's turn"""
        if not self.game_active:
            return
        
        current = self.players[self.current_player]
        symbol = self.symbols[current]
        
        await self.broadcast({
            'type': 'turn',
            'player': current,
            'symbol': symbol,
            'board': self.board
        })
        
        # Send input prompt to current player
        reader, writer = self.clients[current]
        await self.send_message(writer, {
            'type': 'your_turn',
            'message': 'Enter position (1-9): '
        })
    
    async def handle_move(self, username, position):
        """Handle a player's move"""
        if not self.game_active:
            return
        
        current = self.players[self.current_player]
        
        if username != current:
            return  # Not your turn
        
        try:
            pos = int(position)
            if pos < 1 or pos > 9:
                reader, writer = self.clients[username]
                await self.send_message(writer, {
                    'type': 'invalid',
                    'message': 'Invalid position! Enter 1-9: '
                })
                return
            
            # Check if position is empty
            if self.board[pos - 1] != ' ':
                reader, writer = self.clients[username]
                await self.send_message(writer, {
                    'type': 'invalid',
                    'message': 'Position occupied! Choose another: '
                })
                return
        
        except ValueError:
            reader, writer = self.clients[username]
            await self.send_message(writer, {
                'type': 'invalid',
                'message': 'Invalid input! Enter a number: '
            })
            return
        
        # Make the move
        symbol = self.symbols[username]
        self.board[pos - 1] = symbol
        
        logger.info(f"{username} ({symbol}) placed at position {pos}")
        
        # Broadcast the move
        await self.broadcast({
            'type': 'move_made',
            'player': username,
            'symbol': symbol,
            'position': pos,
            'board': self.board
        })
        
        await asyncio.sleep(0.5)
        
        # Check for winner
        if self.check_winner(symbol):
            self.game_active = False
            self.scores[username] += 1
            
            await self.broadcast({
                'type': 'game_won',
                'winner': username,
                'symbol': symbol,
                'board': self.board,
                'scores': self.scores
            })
            
            await asyncio.sleep(3)
            
            # Check if match over
            if self.current_game >= self.max_games:
                await self.end_match()
            else:
                await self.start_game()
        
        # Check for tie
        elif ' ' not in self.board:
            self.game_active = False
            
            await self.broadcast({
                'type': 'game_tie',
                'board': self.board,
                'scores': self.scores
            })
            
            await asyncio.sleep(3)
            
            # Check if match over
            if self.current_game >= self.max_games:
                await self.end_match()
            else:
                await self.start_game()
        
        else:
            # Continue game - switch player
            self.current_player = 1 - self.current_player
            await asyncio.sleep(0.5)
            await self.next_turn()
    
    def check_winner(self, symbol):
        """Check if the symbol has won"""
        # Winning combinations
        wins = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
            [0, 4, 8], [2, 4, 6]               # Diagonals
        ]
        
        for combo in wins:
            if all(self.board[i] == symbol for i in combo):
                return True
        return False
    
    async def end_match(self):
        """End the match and show final results"""
        # Find winner
        if self.scores[self.players[0]] > self.scores[self.players[1]]:
            winner = self.players[0]
        elif self.scores[self.players[1]] > self.scores[self.players[0]]:
            winner = self.players[1]
        else:
            winner = "TIE"
        
        await self.broadcast({
            'type': 'match_over',
            'scores': self.scores,
            'winner': winner,
            'message': f'Match Over! Winner: {winner}'
        })
        
        logger.info(f"Match ended. Winner: {winner}")
        
        await asyncio.sleep(5)
    
    async def send_message(self, writer, message):
        """Send message to a client"""
        try:
            data = json.dumps(message).encode() + b'\n'
            writer.write(data)
            await writer.drain()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def broadcast(self, message):
        """Broadcast message to all connected clients"""
        tasks = []
        for username, (reader, writer) in self.clients.items():
            tasks.append(self.send_message(writer, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def main():
    parser = argparse.ArgumentParser(description='Tic Tac Toe Server')
    parser.add_argument('--port', type=int, required=True, help='Server port')
    parser.add_argument('--room-id', type=int, required=True, help='Room ID')
    parser.add_argument('--players', type=str, required=True, help='Comma-separated player names')
    parser.add_argument('--game-name', type=str, required=True, help='Game name')
    
    args = parser.parse_args()
    
    players = args.players.split(',')
    
    if len(players) != 2:
        print("Error: This game requires exactly 2 players")
        return
    
    server = TicTacToeServer(args.port, args.room_id, players, args.game_name)
    await server.start()


if __name__ == '__main__':
    asyncio.run(main())
