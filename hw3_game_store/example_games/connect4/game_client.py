#!/usr/bin/env python3
"""
Connect4 Game Client - GUI Version
"""
import tkinter as tk
from tkinter import messagebox
import socket
import threading
import json
import sys
import argparse


class Connect4Client:
    """Connect4 GUI Client"""
    
    def __init__(self, server_host, server_port, username):
        self.server_host = server_host
        self.server_port = server_port
        self.username = username
        
        self.sock = None
        self.player_id = None
        self.player_name = ""
        self.opponent_name = ""
        self.current_player = 0
        self.my_turn = False
        
        self.board = [[' ' for _ in range(7)] for _ in range(6)]
        
        # Create GUI
        self.root = tk.Tk()
        self.root.title("Connect 4")
        self.root.geometry("700x700")
        self.root.resizable(False, False)
        
        self.build_ui()
        
        # Connect to server
        self.root.after(100, self.connect_to_server)
    
    def build_ui(self):
        """Build GUI"""
        # Status frame
        self.status_frame = tk.Frame(self.root, bg='lightgray', height=80)
        self.status_frame.pack(fill='x', side='top')
        
        # Player info
        self.player_label = tk.Label(
            self.status_frame,
            text=f"You: {self.username}",
            font=('Arial', 14, 'bold'),
            bg='lightgray'
        )
        self.player_label.pack(pady=5)
        
        # Status label
        self.status_label = tk.Label(
            self.status_frame,
            text="Connecting...",
            font=('Arial', 12),
            bg='lightgray'
        )
        self.status_label.pack(pady=5)
        
        # Game canvas
        self.canvas = tk.Canvas(
            self.root,
            width=700,
            height=600,
            bg='blue'
        )
        self.canvas.pack()
        
        # Draw board
        self.draw_board()
        
        # Bind click
        self.canvas.bind('<Button-1>', self.on_canvas_click)
    
    def draw_board(self):
        """Draw empty board"""
        self.canvas.delete('all')
        
        # Draw grid
        for row in range(6):
            for col in range(7):
                x = col * 100 + 50
                y = row * 100 + 50
                
                # Draw slot
                self.canvas.create_oval(
                    x - 40, y - 40,
                    x + 40, y + 40,
                    fill='white',
                    outline='darkblue',
                    width=2,
                    tags=f'slot_{row}_{col}'
                )
        
        # Draw pieces
        for row in range(6):
            for col in range(7):
                if self.board[row][col] == '●':
                    self.draw_piece(row, col, 'red')
                elif self.board[row][col] == '○':
                    self.draw_piece(row, col, 'yellow')
    
    def draw_piece(self, row, col, color):
        """Draw a piece"""
        x = col * 100 + 50
        y = row * 100 + 50
        
        self.canvas.create_oval(
            x - 38, y - 38,
            x + 38, y + 38,
            fill=color,
            outline='black',
            width=2
        )
    
    def on_canvas_click(self, event):
        """Handle canvas click"""
        if not self.my_turn:
            return
        
        # Determine column
        col = event.x // 100
        if col < 0 or col >= 7:
            return
        
        # Send move
        self.send_move(col)
    
    def connect_to_server(self):
        """Connect to game server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.server_host, self.server_port))
            
            # Start receive thread
            recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
            recv_thread.start()
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {e}")
            self.root.quit()
    
    def receive_loop(self):
        """Receive messages from server"""
        buffer = ""
        
        while True:
            try:
                data = self.sock.recv(1024).decode()
                if not data:
                    break
                
                buffer += data
                
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    try:
                        msg = json.loads(line)
                        self.root.after(0, lambda m=msg: self.handle_message(m))
                    except:
                        pass
            
            except Exception as e:
                break
        
        self.root.after(0, lambda: messagebox.showinfo("Disconnected", "Connection to server lost"))
        self.root.after(100, self.root.quit)
    
    def handle_message(self, msg):
        """Handle server message"""
        msg_type = msg.get('type')
        
        if msg_type == 'welcome':
            self.player_id = msg['player_id']
            self.player_name = msg['player_name']
            self.opponent_name = msg.get('opponent', 'Waiting...')
            
            symbol = '●' if self.player_id == 0 else '○'
            color = 'Red' if self.player_id == 0 else 'Yellow'
            
            self.player_label.config(text=f"You: {self.player_name} ({color} {symbol})")
            self.status_label.config(text=f"Opponent: {self.opponent_name}\nWaiting for game to start...")
        
        elif msg_type == 'start':
            self.current_player = msg['current_player']
            self.update_turn_display()
        
        elif msg_type == 'move':
            player = msg['player']
            row = msg['row']
            col = msg['column']
            
            self.board[row][col] = '●' if player == 0 else '○'
            self.draw_board()
        
        elif msg_type == 'next_turn':
            self.current_player = msg['current_player']
            self.update_turn_display()
        
        elif msg_type == 'game_over':
            winner = msg.get('winner')
            
            if winner is None:
                result = "It's a draw!"
            elif winner == self.player_id:
                result = "You won! 🎉"
            else:
                result = "You lost. Better luck next time!"
            
            self.status_label.config(text=f"Game Over: {result}")
            messagebox.showinfo("Game Over", result)
    
    def update_turn_display(self):
        """Update turn display"""
        self.my_turn = (self.current_player == self.player_id)
        
        if self.my_turn:
            self.status_label.config(
                text="Your turn! Click a column to drop your piece.",
                fg='green'
            )
        else:
            self.status_label.config(
                text=f"{self.opponent_name}'s turn...",
                fg='red'
            )
    
    def send_move(self, column):
        """Send move to server"""
        msg = json.dumps({
            'type': 'move',
            'column': column
        }) + '\n'
        
        try:
            self.sock.sendall(msg.encode())
            self.my_turn = False
            self.status_label.config(text="Waiting for opponent...")
        except:
            pass
    
    def run(self):
        """Run client"""
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default='localhost')
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--username', required=True)
    args = parser.parse_args()
    
    client = Connect4Client(args.server, args.port, args.username)
    client.run()


if __name__ == '__main__':
    main()
