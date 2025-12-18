#!/usr/bin/env python3
"""
Tic Tac Toe Battle - Game Client
CLI client for 2-player tic-tac-toe
"""
import asyncio
import json
import argparse
import sys

class TicTacToeClient:
    def __init__(self, server, port, username):
        self.server = server
        self.port = port
        self.username = username
        
        self.reader = None
        self.writer = None
        self.connected = False
        
        self.my_symbol = ''
        self.players = []
        self.scores = {}
    
    def draw_board(self, board):
        """Draw the tic-tac-toe board"""
        print("\n" + "="*40)
        print("       TIC TAC TOE")
        print("="*40)
        print()
        print("     |     |     ")
        print(f"  {board[0]}  |  {board[1]}  |  {board[2]}  ")
        print("     |     |     ")
        print("-----|-----|-----")
        print("     |     |     ")
        print(f"  {board[3]}  |  {board[4]}  |  {board[5]}  ")
        print("     |     |     ")
        print("-----|-----|-----")
        print("     |     |     ")
        print(f"  {board[6]}  |  {board[7]}  |  {board[8]}  ")
        print("     |     |     ")
        print()
    
    def draw_reference(self):
        """Draw position reference"""
        print("\nPosition Reference:")
        print("     |     |     ")
        print("  1  |  2  |  3  ")
        print("     |     |     ")
        print("-----|-----|-----")
        print("     |     |     ")
        print("  4  |  5  |  6  ")
        print("     |     |     ")
        print("-----|-----|-----")
        print("     |     |     ")
        print("  7  |  8  |  9  ")
        print("     |     |     ")
    
    async def connect_and_play(self):
        """Connect to server and handle game"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.server, self.port
            )
            
            self.connected = True
            print(f"✓ Connected to server at {self.server}:{self.port}")
            print("="*60)
            
            # Send join message
            await self.send_message({
                'type': 'join',
                'username': self.username
            })
            
            # Create task for reading messages
            read_task = asyncio.create_task(self.read_messages())
            
            await read_task
        
        except Exception as e:
            print(f"✗ Connection error: {e}")
        finally:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
    
    async def read_messages(self):
        """Read and handle messages from server"""
        try:
            while True:
                data = await self.reader.read(4096)
                if not data:
                    break
                
                # Handle multiple messages
                messages = data.decode().strip().split('\n')
                for msg_str in messages:
                    if msg_str:
                        message = json.loads(msg_str)
                        await self.handle_message(message)
        
        except Exception as e:
            print(f"\n✗ Error reading messages: {e}")
    
    async def handle_message(self, message):
        """Handle message from server"""
        msg_type = message['type']
        
        if msg_type == 'welcome':
            self.my_symbol = message['symbol']
            self.players = message['players']
            max_games = message['max_games']
            
            print(f"\n{message['message']}")
            print(f"Your symbol: {self.my_symbol}")
            print(f"Players: {self.players[0]} (X) vs {self.players[1]} (O)")
            print(f"Best of {max_games} games")
            print("="*60)
        
        elif msg_type == 'waiting':
            print(f"\n{message['message']}")
        
        elif msg_type == 'game_start':
            print(f"\n{'='*60}")
            print(f"🎮 {message['message']}")
            print(f"{'='*60}")
        
        elif msg_type == 'new_game':
            game_num = message['game']
            max_games = message['max_games']
            scores = message['scores']
            board = message['board']
            
            print(f"\n{'='*60}")
            print(f"📊 GAME {game_num}/{max_games}")
            print(f"{'='*60}")
            print(f"\nCurrent Scores:")
            for player, score in scores.items():
                marker = " ← YOU" if player == self.username else ""
                print(f"  {player}: {score} wins{marker}")
            print(f"{'='*60}")
            
            self.draw_board(board)
            self.draw_reference()
        
        elif msg_type == 'turn':
            player = message['player']
            symbol = message['symbol']
            board = message['board']
            
            self.draw_board(board)
            
            if player == self.username:
                print(f"\n>> YOUR TURN ({symbol})")
            else:
                print(f"\n>> {player}'s turn ({symbol})...")
        
        elif msg_type == 'your_turn':
            # Time to input move
            await self.get_move()
        
        elif msg_type == 'move_made':
            player = message['player']
            symbol = message['symbol']
            position = message['position']
            board = message['board']
            
            if player == self.username:
                print(f"\n✓ You placed {symbol} at position {position}")
            else:
                print(f"\n{player} placed {symbol} at position {position}")
            
            self.draw_board(board)
        
        elif msg_type == 'game_won':
            winner = message['winner']
            symbol = message['symbol']
            board = message['board']
            scores = message['scores']
            
            self.draw_board(board)
            
            print(f"\n{'='*60}")
            if winner == self.username:
                print(f"🏆 YOU WIN! 🏆")
            else:
                print(f"😔 {winner} wins")
            print(f"{'='*60}")
            
            print(f"\nScores:")
            for player, score in scores.items():
                marker = " (YOU)" if player == self.username else ""
                print(f"  {player}: {score} wins{marker}")
        
        elif msg_type == 'game_tie':
            board = message['board']
            scores = message['scores']
            
            self.draw_board(board)
            
            print(f"\n{'='*60}")
            print(f"🤝 IT'S A TIE! 🤝")
            print(f"{'='*60}")
            
            print(f"\nScores:")
            for player, score in scores.items():
                marker = " (YOU)" if player == self.username else ""
                print(f"  {player}: {score} wins{marker}")
        
        elif msg_type == 'match_over':
            scores = message['scores']
            winner = message['winner']
            
            print(f"\n{'='*60}")
            print(f"🏁 MATCH OVER")
            print(f"{'='*60}")
            
            print(f"\nFinal Scores:")
            for player, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                winner_marker = " 🏆" if player == winner else ""
                you_marker = " (YOU)" if player == self.username else ""
                print(f"  {player}: {score} wins{winner_marker}{you_marker}")
            
            print(f"\n{message['message']}")
            print(f"{'='*60}")
            
            if winner == self.username:
                print(f"\n🎉 CONGRATULATIONS! YOU WIN THE MATCH! 🎉")
            elif winner == "TIE":
                print(f"\n🤝 IT'S A TIE MATCH! 🤝")
            else:
                print(f"\n😔 Better luck next time!")
            
            print(f"{'='*60}\n")
        
        elif msg_type == 'invalid':
            print(f"\n✗ {message['message']}", end='', flush=True)
            await self.get_move()
    
    async def get_move(self):
        """Get move from user"""
        try:
            # Read input in a non-blocking way
            loop = asyncio.get_event_loop()
            move = await loop.run_in_executor(None, input, "\nEnter position (1-9): ")
            
            # Send move to server
            await self.send_message({
                'type': 'move',
                'position': move
            })
        except Exception as e:
            print(f"Error getting input: {e}")
    
    async def send_message(self, message):
        """Send message to server"""
        if self.writer:
            data = json.dumps(message).encode() + b'\n'
            self.writer.write(data)
            await self.writer.drain()
    
    def run(self):
        """Run the client"""
        try:
            asyncio.run(self.connect_and_play())
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")


def main():
    parser = argparse.ArgumentParser(description='Tic Tac Toe Client')
    parser.add_argument('--server', type=str, default='localhost', help='Server address')
    parser.add_argument('--port', type=int, required=True, help='Server port')
    parser.add_argument('--username', type=str, required=True, help='Your username')
    
    args = parser.parse_args()
    
    # Print welcome banner
    print("="*60)
    print("    ⭕ TIC TAC TOE BATTLE ❌")
    print("="*60)
    print(f"Player: {args.username}")
    print(f"Server: {args.server}:{args.port}")
    print("="*60)
    
    client = TicTacToeClient(args.server, args.port, args.username)
    client.run()


if __name__ == '__main__':
    main()
