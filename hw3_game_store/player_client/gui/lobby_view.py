"""
Lobby View - Create and join game rooms (P3)
"""
import customtkinter as ctk
import threading
import logging

logger = logging.getLogger(__name__)


class LobbyView(ctk.CTkFrame):
    """Game lobby view"""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.rooms = []
        self._is_active = True  # Flag to prevent operations after cleanup
        
        self.build_ui()
        self.load_rooms()
    
    def build_ui(self):
        """Build lobby UI"""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        
        title = ctk.CTkLabel(
            header,
            text="🎲 Game Lobby",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(side="left")
        
        # Create Room button
        create_btn = ctk.CTkButton(
            header,
            text="+ Create Room",
            command=self.create_room,
            fg_color="green",
            width=150
        )
        create_btn.pack(side="right", padx=5)
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            header,
            text="🔄 Refresh",
            width=100,
            command=self.load_rooms
        )
        refresh_btn.pack(side="right", padx=5)
        
        # Room list
        self.rooms_frame = ctk.CTkScrollableFrame(self, label_text="Available Rooms")
        self.rooms_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    def load_rooms(self):
        """Load room list from server"""
        if not self._is_active:
            return
        
        # Clear existing
        for widget in self.rooms_frame.winfo_children():
            widget.destroy()
        
        loading = ctk.CTkLabel(self.rooms_frame, text="Loading rooms...")
        loading.pack(pady=20)
        
        def load_thread():
            if not self._is_active:
                return
            
            try:
                rooms = self.app.network.get_room_list()
                if self._is_active:
                    self.after(0, lambda: self.display_rooms(rooms) if self._is_active else None)
            except Exception as e:
                logger.error(f"Error loading rooms: {e}")
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def display_rooms(self, rooms):
        """Display rooms"""
        if not self._is_active:
            return
        
        # Clear
        for widget in self.rooms_frame.winfo_children():
            widget.destroy()
        
        self.rooms = rooms
        
        if not rooms:
            no_rooms = ctk.CTkLabel(
                self.rooms_frame,
                text="No active rooms.\nCreate one to start playing!",
                font=ctk.CTkFont(size=14)
            )
            no_rooms.pack(pady=50)
            return
        
        for room in rooms:
            self.create_room_card(room)
    
    def create_room_card(self, room):
        """Create room card"""
        card = ctk.CTkFrame(self.rooms_frame, corner_radius=10)
        card.pack(fill="x", padx=5, pady=5)
        
        # Left: Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)
        
        # Room name
        title = ctk.CTkLabel(
            info_frame,
            text=room['name'],
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.pack(anchor="w")
        
        # Game info
        game_info = f"🎮 {room['game_name']} | Host: {room['host_name']}"
        ctk.CTkLabel(info_frame, text=game_info).pack(anchor="w", pady=2)
        
        # Players
        players_text = f"👥 {room['current_players']}/{room['max_players']} players"
        ctk.CTkLabel(info_frame, text=players_text).pack(anchor="w")
        
        # Status badge
        status_color = {
            'waiting': 'green',
            'playing': 'orange',
            'closed': 'red'
        }.get(room['status'], 'gray')
        
        status_label = ctk.CTkLabel(
            info_frame,
            text=f"[{room['status'].upper()}]",
            text_color=status_color,
            font=ctk.CTkFont(size=11)
        )
        status_label.pack(anchor="w", pady=2)
        
        # Right: Action
        if room['status'] == 'waiting' and room['current_players'] < room['max_players']:
            join_btn = ctk.CTkButton(
                card,
                text="Join",
                width=80,
                command=lambda r=room: self.join_room(r)
            )
            join_btn.pack(side="right", padx=10)
    
    def create_room(self):
        """Open create room dialog"""
        # Check if already in a room
        if self.app.current_room:
            self.app.show_error(
                "You are already in a room!\n"
                "Please leave your current room first."
            )
            return
        
        CreateRoomDialog(self.app, self.load_rooms)
    
    def join_room(self, room):
        """Join a room"""
        # Check if already in a room
        if self.app.current_room:
            self.app.show_error(
                "You are already in a room!\n"
                "Please leave your current room first."
            )
            return
        
        success, message = self.app.network.join_room(room['id'])
        
        if success:
            # Switch to room view
            self.app.show_room_view(room)
        else:
            self.app.show_error(f"Failed to join room:\n{message}")
    
    def on_room_update(self, data):
        """Handle room update notification"""
        if self._is_active:
            self.load_rooms()
    
    def cleanup(self):
        """Clean up resources before destroying view"""
        logger.info("LobbyView cleanup called")
        self._is_active = False


class CreateRoomDialog(ctk.CTkToplevel):
    """Create room dialog"""
    
    def __init__(self, app, on_success_callback=None):
        super().__init__(app)
        self.app = app
        self.on_success = on_success_callback
        
        self.title("Create Game Room")
        self.geometry("500x400")
        
        # Build UI first
        self.build_ui()
        self.load_games()
        
        # Make modal - after UI is built
        self.transient(app)
        self.update_idletasks()
        self.after(10, self.grab_set)
    
    def build_ui(self):
        """Build UI"""
        # Title
        title = ctk.CTkLabel(
            self,
            text="Create New Room",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        # Room name
        ctk.CTkLabel(self, text="Room Name:").pack(pady=5)
        self.room_name_entry = ctk.CTkEntry(self, width=300)
        self.room_name_entry.pack(pady=5)
        self.room_name_entry.insert(0, f"{self.app.current_user}'s Room")
        
        # Game selection
        ctk.CTkLabel(self, text="Select Game:").pack(pady=5)
        self.game_menu = ctk.CTkOptionMenu(self, values=["Loading..."], width=300)
        self.game_menu.pack(pady=5)
        
        # Max players
        ctk.CTkLabel(self, text="Max Players:").pack(pady=5)
        self.max_players_var = ctk.IntVar(value=4)
        self.max_players_slider = ctk.CTkSlider(
            self,
            from_=2,
            to=8,
            number_of_steps=6,
            variable=self.max_players_var,
            width=300
        )
        self.max_players_slider.pack(pady=5)
        
        self.max_players_label = ctk.CTkLabel(self, text="4 players")
        self.max_players_label.pack()
        self.max_players_var.trace('w', self.update_players_label)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        create_btn = ctk.CTkButton(
            btn_frame,
            text="Create Room",
            command=self.do_create,
            fg_color="green",
            width=120
        )
        create_btn.pack(side="left", padx=10)
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            width=120
        )
        cancel_btn.pack(side="left", padx=10)
        
        # Status
        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.pack(pady=10)
    
    def load_games(self):
        """Load available games"""
        def load_thread():
            games = self.app.network.get_game_list()
            self.after(0, lambda: self.set_games(games))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def set_games(self, games):
        """Set game options"""
        if not games:
            self.game_menu.configure(values=["No games available"])
            return
        
        self.games = games
        game_names = [f"{g['name']} (v{g['version']})" for g in games]
        self.game_menu.configure(values=game_names)
        self.game_menu.set(game_names[0])
    
    def update_players_label(self, *args):
        """Update players label"""
        count = self.max_players_var.get()
        self.max_players_label.configure(text=f"{count} players")
    
    def do_create(self):
        """Create room"""
        room_name = self.room_name_entry.get().strip()
        if not room_name:
            self.status_label.configure(text="Please enter room name", text_color="red")
            return
        
        if not hasattr(self, 'games') or not self.games:
            self.status_label.configure(text="No games available", text_color="red")
            return
        
        # Get selected game
        selected_idx = self.game_menu.cget("values").index(self.game_menu.get())
        game = self.games[selected_idx]
        
        max_players = self.max_players_var.get()
        
        self.status_label.configure(text="Creating room...")
        
        def create_thread():
            result = self.app.network.create_room(game['id'], room_name, max_players)
            self.after(0, lambda: self.on_create_result(result))
        
        threading.Thread(target=create_thread, daemon=True).start()
    
    def on_create_result(self, result):
        """Handle create result"""
        if result:
            self.status_label.configure(
                text=f"✓ Room created! Code: {result['room_code']}",
                text_color="green"
            )
            
            # Prepare room data for room view
            room_data = {
                'id': result.get('room_id'),
                'room_id': result.get('room_id'),
                'room_name': result.get('room_name'),
                'room_code': result.get('room_code'),
                'game_name': '[Game Name]',  # Will be populated
                'host_name': self.app.network.user_info.get('username') if self.app.network.user_info else 'You',
                'host_id': self.app.network.user_info.get('id') if self.app.network.user_info else 0,
                'current_players': 1,
                'max_players': self.max_players_var.get(),
                'status': 'waiting'
            }
            
            # Close dialog and switch to room view
            self.destroy()
            self.app.show_room_view(room_data)
        else:
            self.status_label.configure(text="Failed to create room", text_color="red")