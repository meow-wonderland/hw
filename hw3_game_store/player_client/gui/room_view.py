"""
Room View - Display players in room and start game (P3)
"""
import customtkinter as ctk
import threading
import logging

logger = logging.getLogger(__name__)


class RoomView(ctk.CTkFrame):
    """Room waiting view"""
    
    def __init__(self, parent, app, room_data):
        super().__init__(parent)
        self.app = app
        self.room_data = room_data
        self.is_host = False  # Will be set based on user
        self.refresh_job = None  # For periodic refresh
        self._is_active = True  # Flag to prevent operations after cleanup
        
        self.build_ui()
        self.load_room_info()
        
        # Start periodic refresh (every 3 seconds)
        self.start_refresh_timer()
    
    def build_ui(self):
        """Build room UI"""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        
        title = ctk.CTkLabel(
            header,
            text=f"🎮 {self.room_data.get('room_name', 'Game Room')}",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(side="left")
        
        # Leave button
        leave_btn = ctk.CTkButton(
            header,
            text="← Leave Room",
            command=self.leave_room,
            fg_color="red",
            width=120
        )
        leave_btn.pack(side="right")
        
        # Game info
        info_frame = ctk.CTkFrame(self, corner_radius=10)
        info_frame.pack(fill="x", padx=10, pady=10)
        
        game_name = self.room_data.get('game_name', 'Unknown Game')
        host_name = self.room_data.get('host_name', 'Unknown')
        room_code = self.room_data.get('room_code', 'N/A')
        
        ctk.CTkLabel(
            info_frame,
            text=f"Game: {game_name}",
            font=ctk.CTkFont(size=16)
        ).pack(pady=5)
        
        ctk.CTkLabel(
            info_frame,
            text=f"Host: {host_name}",
            font=ctk.CTkFont(size=14)
        ).pack(pady=2)
        
        ctk.CTkLabel(
            info_frame,
            text=f"Room Code: {room_code}",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        ).pack(pady=2)
        
        # Players section
        players_label = ctk.CTkLabel(
            self,
            text="👥 Players in Room",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        players_label.pack(pady=(20, 10))
        
        # Players list
        self.players_frame = ctk.CTkFrame(self, corner_radius=10)
        self.players_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Bottom actions
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.pack(fill="x", side="bottom", padx=10, pady=10)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            actions_frame,
            text="Waiting for players...",
            font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(pady=10)
        
        # Start button (only for host)
        self.start_btn = ctk.CTkButton(
            actions_frame,
            text="🎮 Start Game",
            command=self.start_game,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="green",
            height=45,
            width=200
        )
        # Will show/hide based on host status
    
    def load_room_info(self):
        """Load room information in background"""
        def load_thread():
            # Check if current user is host
            if self.app.network.user_info:
                user_id = self.app.network.user_info.get('id')
                self.is_host = (user_id == self.room_data.get('host_id'))
            
            # Show start button only for host
            if self.is_host and self._is_active:
                self.after(0, lambda: self.start_btn.pack(pady=10) if self._is_active else None)
                self.after(0, lambda: self.status_label.configure(text="Click 'Start Game' when ready!") if self._is_active else None)
            
            # Refresh player list
            if self._is_active:
                self.after(0, self.refresh_players)
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def refresh_players(self):
        """Refresh player list"""
        if not self._is_active:
            return
        
        # Clear current players
        for widget in self.players_frame.winfo_children():
            widget.destroy()
        
        # Get updated data
        max_players = self.room_data.get('max_players', 4)
        current = self.room_data.get('current_players', 1)
        
        # Get actual player names if available
        players = self.room_data.get('players', [])
        host_name = self.room_data.get('host_name', 'Host')
        
        # Display player slots
        for i in range(max_players):
            slot_frame = ctk.CTkFrame(self.players_frame, corner_radius=5)
            slot_frame.pack(fill="x", padx=10, pady=5)
            
            if i < current:
                # Occupied slot
                if i < len(players):
                    player_name = players[i]
                elif i == 0:
                    player_name = host_name
                else:
                    player_name = f"Player {i+1}"
                
                # Add crown for host
                if i == 0:
                    player_name += " 👑"
                
                ctk.CTkLabel(
                    slot_frame,
                    text=player_name,
                    font=ctk.CTkFont(size=14),
                    text_color="lightgreen"
                ).pack(side="left", padx=10, pady=8)
                
                ctk.CTkLabel(
                    slot_frame,
                    text="✓ Ready",
                    text_color="green"
                ).pack(side="right", padx=10)
            else:
                # Empty slot
                ctk.CTkLabel(
                    slot_frame,
                    text=f"[Waiting for Player {i+1}...]",
                    font=ctk.CTkFont(size=14),
                    text_color="gray"
                ).pack(side="left", padx=10, pady=8)
    
    def start_game(self):
        """Start the game (host only)"""
        if not self.is_host:
            self.app.show_error("Only the host can start the game!")
            return
        
        if not self._is_active:
            return
        
        self.status_label.configure(text="Starting game...")
        self.start_btn.configure(state="disabled")
        
        def start_thread():
            # Send start game request
            room_id = self.room_data.get('room_id') or self.room_data.get('id')
            
            success, message = self.app.network.start_game(room_id)
            
            if success and self._is_active:
                # Game will be launched via GAME_STARTED message
                self.after(0, lambda: self.status_label.configure(
                    text="✓ Game starting! Launching client..."
                ) if self._is_active else None)
            elif self._is_active:
                self.after(0, lambda: self.app.show_error(f"Failed to start:\n{message}") if self._is_active else None)
                self.after(0, lambda: self.start_btn.configure(state="normal") if self._is_active else None)
                self.after(0, lambda: self.status_label.configure(text="Click 'Start Game' when ready!") if self._is_active else None)
        
        threading.Thread(target=start_thread, daemon=True).start()
    
    def leave_room(self):
        """Leave the current room"""
        # Mark as inactive
        self._is_active = False
        
        # Stop refresh timer
        if self.refresh_job:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None
        
        room_id = self.room_data.get('room_id') or self.room_data.get('id')
        
        # Send leave room request
        success, message = self.app.network.leave_room(room_id)
        
        if success or True:  # Always return to lobby even if request fails
            # Clear current room
            self.app.current_room = None
            
            # Return to lobby
            self.app.show_view('lobby')
        else:
            self.app.show_error(f"Failed to leave room:\n{message}")
    
    def start_refresh_timer(self):
        """Start periodic room refresh"""
        if not self._is_active:
            return
        
        self.refresh_room_data()
        # Schedule next refresh in 3 seconds
        if self._is_active:
            self.refresh_job = self.after(3000, self.start_refresh_timer)
    
    def refresh_room_data(self):
        """Refresh room data from server"""
        if not self._is_active:
            return
        
        def refresh_thread():
            if not self._is_active:
                return
            
            try:
                room_id = self.room_data.get('room_id') or self.room_data.get('id')
                # Get updated room info
                room_list = self.app.network.get_room_list()
                
                if not self._is_active:
                    return
                
                # Find this room
                for room in room_list:
                    if room.get('id') == room_id:
                        # Update room data
                        self.room_data.update(room)
                        # Update UI on main thread
                        if self._is_active:
                            self.after(0, self.refresh_players)
                        return
                
                # Room not found - might have been closed
                logger.warning(f"Room {room_id} not found in room list")
                if self._is_active:
                    self.after(0, lambda: self.app.show_error(
                        "Room was closed.\nReturning to lobby..."
                    ) if self._is_active else None)
                    self.after(2000, self.leave_room)
            except Exception as e:
                logger.error(f"Error refreshing room data: {e}")
        
        threading.Thread(target=refresh_thread, daemon=True).start()
    
    def cleanup(self):
        """Clean up resources before destroying view"""
        logger.info("RoomView cleanup called")
        self._is_active = False
        
        # Stop refresh timer
        if self.refresh_job:
            try:
                self.after_cancel(self.refresh_job)
            except Exception as e:
                logger.error(f"Error canceling refresh job: {e}")
            self.refresh_job = None