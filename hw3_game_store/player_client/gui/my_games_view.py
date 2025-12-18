"""
My Games View - View downloaded games (P2)
"""
import customtkinter as ctk


class MyGamesView(ctk.CTkFrame):
    """My downloaded games view"""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        self.build_ui()
        self.load_games()
    
    def build_ui(self):
        """Build UI"""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        
        title = ctk.CTkLabel(
            header,
            text="💾 My Games",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(side="left")
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            header,
            text="🔄 Refresh",
            width=100,
            command=self.load_games
        )
        refresh_btn.pack(side="right")
        
        # Games list
        self.games_frame = ctk.CTkScrollableFrame(self, label_text="Installed Games")
        self.games_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    def load_games(self):
        """Load installed games"""
        # Clear
        for widget in self.games_frame.winfo_children():
            widget.destroy()
        
        installed = self.app.download_manager.get_installed_games()
        
        if not installed:
            no_games = ctk.CTkLabel(
                self.games_frame,
                text="No games installed yet.\nVisit the Store to download games!",
                font=ctk.CTkFont(size=14)
            )
            no_games.pack(pady=50)
            return
        
        for game in installed:
            self.create_game_card(game)
    
    def create_game_card(self, game):
        """Create game card"""
        card = ctk.CTkFrame(self.games_frame, corner_radius=10)
        card.pack(fill="x", padx=5, pady=5)
        
        # Left: Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)
        
        # Name
        title = ctk.CTkLabel(
            info_frame,
            text=game['name'],
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(anchor="w")
        
        # Version
        version_label = ctk.CTkLabel(
            info_frame,
            text=f"Installed version: {game['version']}",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        version_label.pack(anchor="w", pady=2)
        
        # Path
        path_label = ctk.CTkLabel(
            info_frame,
            text=f"📁 {game['path']}",
            font=ctk.CTkFont(size=10),
            text_color="darkgray"
        )
        path_label.pack(anchor="w", pady=2)
        
        # Right: Actions
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(side="right", padx=10, pady=10)
        
        # Check for updates button
        update_btn = ctk.CTkButton(
            actions,
            text="🔄 Check Updates",
            width=120,
            command=lambda g=game: self.check_updates(g)
        )
        update_btn.pack(pady=3)
        
        # Play button (if available)
        play_btn = ctk.CTkButton(
            actions,
            text="▶️ Play",
            width=120,
            fg_color="green",
            command=lambda g=game: self.play_game(g)
        )
        play_btn.pack(pady=3)
    
    def check_updates(self, game):
        """Check for game updates"""
        # This would connect to server to check
        self.app.show_info(f"Checking updates for {game['name']}...")
        
        # TODO: Implement update check
    
    def play_game(self, game):
        """Play game (go to lobby)"""
        self.app.show_info(
            f"To play {game['name']}, please:\n\n"
            f"1. Go to the Lobby\n"
            f"2. Create or join a room for this game\n"
            f"3. Wait for the host to start"
        )
        self.app.show_lobby()
