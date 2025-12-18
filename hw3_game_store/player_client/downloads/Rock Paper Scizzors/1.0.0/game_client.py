#!/usr/bin/env python3
"""
Rock Paper Scissors Tournament - Game Client
GUI client for 3-player rock-paper-scissors
"""
import asyncio
import json
import argparse
import tkinter as tk
from tkinter import messagebox
import threading

class RPSClient:
    def __init__(self, server, port, username):
        self.server = server
        self.port = port
        self.username = username
        
        self.reader = None
        self.writer = None
        self.connected = False
        
        self.players = []
        self.scores = {}
        self.current_round = 0
        self.max_rounds = 0
        self.my_choice = None
        self.round_active = False
        
        # Create GUI
        self.root = tk.Tk()
        self.root.title(f"Rock Paper Scissors - {username}")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        self.create_ui()
        
        # Start connection in background
        threading.Thread(target=self.run_async_loop, daemon=True).start()
    
    def create_ui(self):
        """Create the GUI"""
        # Title
        title = tk.Label(
            self.root,
            text="🎮 Rock Paper Scissors Tournament",
            font=("Arial", 20, "bold"),
            bg="#2c3e50",
            fg="white",
            pady=15
        )
        title.pack(fill=tk.X)
        
        # Status
        self.status_label = tk.Label(
            self.root,
            text="Connecting...",
            font=("Arial", 12),
            fg="#3498db"
        )
        self.status_label.pack(pady=10)
        
        # Round info
        self.round_label = tk.Label(
            self.root,
            text="Waiting for game to start...",
            font=("Arial", 14, "bold")
        )
        self.round_label.pack(pady=5)
        
        # Scores
        self.score_frame = tk.Frame(self.root, bg="#ecf0f1", padx=10, pady=10)
        self.score_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.score_labels = {}
        
        # Choice buttons
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=20)
        
        # Rock button
        self.rock_btn = tk.Button(
            self.button_frame,
            text="🪨\nROCK",
            font=("Arial", 16, "bold"),
            width=8,
            height=3,
            bg="#e74c3c",
            fg="white",
            command=lambda: self.make_choice("rock"),
            state=tk.DISABLED
        )
        self.rock_btn.grid(row=0, column=0, padx=10)
        
        # Paper button
        self.paper_btn = tk.Button(
            self.button_frame,
            text="📄\nPAPER",
            font=("Arial", 16, "bold"),
            width=8,
            height=3,
            bg="#3498db",
            fg="white",
            command=lambda: self.make_choice("paper"),
            state=tk.DISABLED
        )
        self.paper_btn.grid(row=0, column=1, padx=10)
        
        # Scissors button
        self.scissors_btn = tk.Button(
            self.button_frame,
            text="✂️\nSCISSORS",
            font=("Arial", 16, "bold"),
            width=8,
            height=3,
            bg="#2ecc71",
            fg="white",
            command=lambda: self.make_choice("scissors"),
            state=tk.DISABLED
        )
        self.scissors_btn.grid(row=0, column=2, padx=10)
        
        # Result area
        self.result_text = tk.Text(
            self.root,
            height=8,
            width=60,
            font=("Arial", 10),
            state=tk.DISABLED,
            bg="#ecf0f1"
        )
        self.result_text.pack(padx=20, pady=10)
    
    def run_async_loop(self):
        """Run async event loop in thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.connect_and_play())
    
    async def connect_and_play(self):
        """Connect to server and handle game"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.server, self.port
            )
            
            self.connected = True
            self.update_status("Connected to server")
            
            # Send join message
            await self.send_message({
                'type': 'join',
                'username': self.username
            })
            
            # Handle messages
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
            self.update_status(f"Connection error: {e}")
        finally:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
    
    async def handle_message(self, message):
        """Handle message from server"""
        msg_type = message['type']
        
        if msg_type == 'welcome':
            self.players = message['players']
            self.max_rounds = message['max_rounds']
            self.update_status(message['message'])
            self.update_scores({p: 0 for p in self.players})
        
        elif msg_type == 'waiting':
            self.update_status(message['message'])
        
        elif msg_type == 'game_start':
            self.update_status(message['message'])
            self.add_result(message['message'])
        
        elif msg_type == 'round_start':
            self.current_round = message['round']
            self.max_rounds = message['max_rounds']
            self.scores = message['scores']
            self.my_choice = None
            self.round_active = True
            
            self.root.after(0, lambda: self.round_label.config(
                text=f"Round {self.current_round}/{self.max_rounds}"
            ))
            self.update_scores(self.scores)
            self.enable_buttons()
            self.add_result(f"\n{'='*50}\n{message['message']}\n{'='*50}")
        
        elif msg_type == 'player_ready':
            username = message['username']
            ready = message['ready_count']
            total = message['total_players']
            self.add_result(f"{username} made their choice! ({ready}/{total} ready)")
        
        elif msg_type == 'reveal':
            choices = message['choices']
            self.add_result("\n🎲 Choices revealed:")
            for player, choice in choices.items():
                emoji = {'rock': '🪨', 'paper': '📄', 'scissors': '✂️'}
                self.add_result(f"  {player}: {emoji[choice]} {choice.upper()}")
        
        elif msg_type == 'round_result':
            results = message['results']
            scores = message['scores']
            
            self.add_result("\n📊 Round results:")
            for player, result in results.items():
                if result == 'winner':
                    self.add_result(f"  🏆 {player} WINS! (+2 points)")
                elif result == 'partial':
                    self.add_result(f"  ✨ {player} partial win (+1 point)")
                else:
                    self.add_result(f"  {player} loses (0 points)")
            
            self.update_scores(scores)
            self.round_active = False
        
        elif msg_type == 'game_over':
            winners = message['winners']
            scores = message['scores']
            
            self.add_result(f"\n\n🎉 {message['message']} 🎉")
            self.add_result("\nFinal Scores:")
            for player, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                self.add_result(f"  {player}: {score} points")
            
            self.update_status("Game Over!")
            self.root.after(0, lambda: messagebox.showinfo(
                "Game Over",
                f"Winner(s): {', '.join(winners)}\n\nFinal scores:\n" + 
                "\n".join(f"{p}: {s}" for p, s in scores.items())
            ))
    
    def make_choice(self, choice):
        """Make a choice"""
        if not self.round_active or self.my_choice:
            return
        
        self.my_choice = choice
        self.disable_buttons()
        
        # Send choice
        asyncio.run_coroutine_threadsafe(
            self.send_message({'type': 'choice', 'choice': choice}),
            asyncio.get_event_loop()
        )
        
        emoji = {'rock': '🪨', 'paper': '📄', 'scissors': '✂️'}
        self.add_result(f"\n✓ You chose: {emoji[choice]} {choice.upper()}")
    
    def enable_buttons(self):
        """Enable choice buttons"""
        self.root.after(0, lambda: [
            self.rock_btn.config(state=tk.NORMAL),
            self.paper_btn.config(state=tk.NORMAL),
            self.scissors_btn.config(state=tk.NORMAL)
        ])
    
    def disable_buttons(self):
        """Disable choice buttons"""
        self.root.after(0, lambda: [
            self.rock_btn.config(state=tk.DISABLED),
            self.paper_btn.config(state=tk.DISABLED),
            self.scissors_btn.config(state=tk.DISABLED)
        ])
    
    def update_status(self, text):
        """Update status label"""
        self.root.after(0, lambda: self.status_label.config(text=text))
    
    def update_scores(self, scores):
        """Update score display"""
        def _update():
            # Clear old labels
            for widget in self.score_frame.winfo_children():
                widget.destroy()
            
            # Create new labels
            tk.Label(
                self.score_frame,
                text="🏆 SCORES:",
                font=("Arial", 12, "bold"),
                bg="#ecf0f1"
            ).grid(row=0, column=0, columnspan=3, pady=5)
            
            for i, (player, score) in enumerate(scores.items()):
                color = "#2ecc71" if player == self.username else "#34495e"
                tk.Label(
                    self.score_frame,
                    text=f"{player}: {score}",
                    font=("Arial", 11, "bold" if player == self.username else "normal"),
                    fg=color,
                    bg="#ecf0f1"
                ).grid(row=1, column=i, padx=20)
        
        self.root.after(0, _update)
    
    def add_result(self, text):
        """Add text to result area"""
        def _add():
            self.result_text.config(state=tk.NORMAL)
            self.result_text.insert(tk.END, text + "\n")
            self.result_text.see(tk.END)
            self.result_text.config(state=tk.DISABLED)
        
        self.root.after(0, _add)
    
    async def send_message(self, message):
        """Send message to server"""
        if self.writer:
            data = json.dumps(message).encode() + b'\n'
            self.writer.write(data)
            await self.writer.drain()
    
    def run(self):
        """Run the client"""
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Rock Paper Scissors Client')
    parser.add_argument('--server', type=str, default='localhost', help='Server address')
    parser.add_argument('--port', type=int, required=True, help='Server port')
    parser.add_argument('--username', type=str, required=True, help='Your username')
    
    args = parser.parse_args()
    
    client = RPSClient(args.server, args.port, args.username)
    client.run()


if __name__ == '__main__':
    main()
