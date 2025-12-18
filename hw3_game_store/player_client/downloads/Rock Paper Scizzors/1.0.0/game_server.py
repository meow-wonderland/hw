#!/usr/bin/env python3
"""
Rock Paper Scissors Tournament - Game Server
A 3-player simultaneous rock-paper-scissors game
"""
import asyncio
import json
import argparse
import logging
from enum import Enum

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Choice(Enum):
    ROCK = "rock"
    PAPER = "paper"
    SCISSORS = "scissors"


class GameServer:
    def __init__(self, port, room_id, players, game_name):
        self.port = port
        self.room_id = room_id
        self.players = players
        self.game_name = game_name
        
        self.clients = {}  # username -> (reader, writer)
        self.ready_players = set()
        self.current_round = 0
        self.max_rounds = 5
        self.scores = {player: 0 for player in players}
        self.choices = {}  # username -> choice for current round
        
        logger.info(f"Game server initialized: {game_name} (Room {room_id})")
        logger.info(f"Players: {players}")
    
    async def start(self):
        """Start the game server"""
        server = await asyncio.start_server(
            self.handle_client, 
            '0.0.0.0', 
            self.port
        )
        
        logger.info(f"🎮 Rock Paper Scissors server running on port {self.port}")
        
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
                    'message': f'Welcome to Rock Paper Scissors Tournament!',
                    'players': self.players,
                    'max_rounds': self.max_rounds
                })
                
                # Check if all players connected
                if len(self.clients) == len(self.players):
                    logger.info("All players connected, starting game!")
                    await self.broadcast({
                        'type': 'game_start',
                        'message': 'All players connected! Game starting...'
                    })
                    await asyncio.sleep(2)
                    await self.start_round()
                else:
                    await self.broadcast({
                        'type': 'waiting',
                        'message': f'Waiting for players... ({len(self.clients)}/{len(self.players)})'
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
                
                if msg_type == 'choice':
                    choice = message['choice']
                    await self.handle_choice(username, choice)
                
        except Exception as e:
            logger.error(f"Error in player {username} messages: {e}")
        finally:
            # Player disconnected
            if username in self.clients:
                del self.clients[username]
            logger.info(f"Player {username} disconnected")
    
    async def start_round(self):
        """Start a new round"""
        self.current_round += 1
        self.choices = {}
        
        await self.broadcast({
            'type': 'round_start',
            'round': self.current_round,
            'max_rounds': self.max_rounds,
            'scores': self.scores,
            'message': f'Round {self.current_round}/{self.max_rounds} - Make your choice!'
        })
    
    async def handle_choice(self, username, choice):
        """Handle a player's choice"""
        if username in self.choices:
            return  # Already made choice
        
        self.choices[username] = choice
        logger.info(f"{username} chose {choice}")
        
        # Broadcast that player made choice (without revealing)
        await self.broadcast({
            'type': 'player_ready',
            'username': username,
            'ready_count': len(self.choices),
            'total_players': len(self.players)
        })
        
        # Check if all players made choices
        if len(self.choices) == len(self.players):
            await self.resolve_round()
    
    async def resolve_round(self):
        """Resolve the round and determine winners"""
        # Reveal choices
        await self.broadcast({
            'type': 'reveal',
            'choices': self.choices
        })
        
        await asyncio.sleep(2)
        
        # Calculate winners
        choices_list = list(self.choices.items())
        results = {}
        
        # In 3-player RPS, compare each pair
        for i, (p1, c1) in enumerate(choices_list):
            wins = 0
            for j, (p2, c2) in enumerate(choices_list):
                if i != j:
                    if self.beats(c1, c2):
                        wins += 1
            
            if wins == 2:  # Beat both opponents
                self.scores[p1] += 2
                results[p1] = 'winner'
            elif wins == 1:  # Beat one opponent
                self.scores[p1] += 1
                results[p1] = 'partial'
            else:
                results[p1] = 'loser'
        
        # Broadcast results
        await self.broadcast({
            'type': 'round_result',
            'results': results,
            'scores': self.scores,
            'round': self.current_round
        })
        
        await asyncio.sleep(3)
        
        # Check if game over
        if self.current_round >= self.max_rounds:
            await self.end_game()
        else:
            await self.start_round()
    
    def beats(self, choice1, choice2):
        """Check if choice1 beats choice2"""
        wins = {
            'rock': 'scissors',
            'paper': 'rock',
            'scissors': 'paper'
        }
        return wins.get(choice1) == choice2
    
    async def end_game(self):
        """End the game and show final results"""
        # Find winner(s)
        max_score = max(self.scores.values())
        winners = [p for p, s in self.scores.items() if s == max_score]
        
        await self.broadcast({
            'type': 'game_over',
            'scores': self.scores,
            'winners': winners,
            'message': f"Game Over! Winner(s): {', '.join(winners)}"
        })
        
        logger.info(f"Game ended. Winners: {winners}")
        
        # Wait a bit before closing
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
    parser = argparse.ArgumentParser(description='Rock Paper Scissors Tournament Server')
    parser.add_argument('--port', type=int, required=True, help='Server port')
    parser.add_argument('--room-id', type=int, required=True, help='Room ID')
    parser.add_argument('--players', type=str, required=True, help='Comma-separated player names')
    parser.add_argument('--game-name', type=str, required=True, help='Game name')
    
    args = parser.parse_args()
    
    players = args.players.split(',')
    
    server = GameServer(args.port, args.room_id, players, args.game_name)
    await server.start()


if __name__ == '__main__':
    asyncio.run(main())
