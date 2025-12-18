"""
Store View - Browse and view game details (P1)
"""
import customtkinter as ctk
import threading


class StoreView(ctk.CTkFrame):
    """Game store browsing view"""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.games = []
        
        self.build_ui()
        self.load_games()
    
    def build_ui(self):
        """Build store UI"""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        
        title = ctk.CTkLabel(
            header,
            text="📦 Game Store",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(side="left")
        
        # Search box
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            header,
            placeholder_text="🔍 Search games...",
            width=250,
            textvariable=self.search_var
        )
        self.search_entry.pack(side="right", padx=10)
        self.search_var.trace('w', lambda *args: self.filter_games())
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            header,
            text="🔄",
            width=40,
            command=self.load_games
        )
        refresh_btn.pack(side="right")
        
        # Game list (scrollable)
        self.games_frame = ctk.CTkScrollableFrame(self, label_text="Available Games")
        self.games_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    def load_games(self):
        """Load games from server"""
        # Clear existing
        for widget in self.games_frame.winfo_children():
            widget.destroy()
        
        loading = ctk.CTkLabel(self.games_frame, text="Loading games...")
        loading.pack(pady=20)
        
        def load_thread():
            games = self.app.network.get_game_list()
            self.after(0, lambda: self.display_games(games))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def display_games(self, games):
        """Display games in list"""
        # Clear loading message
        for widget in self.games_frame.winfo_children():
            widget.destroy()
        
        self.games = games
        
        if not games:
            no_games = ctk.CTkLabel(
                self.games_frame,
                text="No games available yet.\nCheck back later!",
                font=ctk.CTkFont(size=14)
            )
            no_games.pack(pady=50)
            return
        
        for game in games:
            self.create_game_card(game)
    
    def filter_games(self):
        """Filter games by search term"""
        search_term = self.search_var.get().lower()
        
        # Clear
        for widget in self.games_frame.winfo_children():
            widget.destroy()
        
        # Filter and display
        filtered = [g for g in self.games if search_term in g['name'].lower() or 
                   search_term in g.get('description', '').lower()]
        
        for game in filtered:
            self.create_game_card(game)
    
    def create_game_card(self, game):
        """Create a game card widget"""
        card = ctk.CTkFrame(self.games_frame, corner_radius=10)
        card.pack(fill="x", padx=5, pady=5)
        
        # Left side: Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)
        
        # Title
        title = ctk.CTkLabel(
            info_frame,
            text=game['name'],
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(anchor="w")
        
        # Description
        desc = game.get('description', 'No description available')
        if len(desc) > 100:
            desc = desc[:100] + "..."
        desc_label = ctk.CTkLabel(
            info_frame,
            text=desc,
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        desc_label.pack(anchor="w", pady=5)
        
        # Metadata
        meta_text = f"v{game['version']} | "
        meta_text += f"⭐ {game['rating']:.1f}/5.0 ({game['rating_count']} reviews) | "
        meta_text += f"👥 {game['min_players']}-{game['max_players']} players | "
        meta_text += f"⬇️ {game['downloads']} downloads"
        
        meta_label = ctk.CTkLabel(
            info_frame,
            text=meta_text,
            font=ctk.CTkFont(size=11)
        )
        meta_label.pack(anchor="w")
        
        # Type badge
        type_badge = ctk.CTkLabel(
            info_frame,
            text=f"[{game['type'].upper()}]",
            font=ctk.CTkFont(size=10),
            text_color="lightblue"
        )
        type_badge.pack(anchor="w", pady=2)
        
        # Right side: Actions
        actions_frame = ctk.CTkFrame(card, fg_color="transparent")
        actions_frame.pack(side="right", padx=10, pady=10)
        
        # Details button
        details_btn = ctk.CTkButton(
            actions_frame,
            text="📖 Details",
            width=100,
            command=lambda g=game: self.show_game_detail(g)
        )
        details_btn.pack(pady=3)
        
        # Download button
        download_btn = ctk.CTkButton(
            actions_frame,
            text="⬇️ Download",
            width=100,
            fg_color="green",
            command=lambda g=game: self.download_game(g)
        )
        download_btn.pack(pady=3)
    
    def show_game_detail(self, game):
        """Show detailed game info dialog (P1)"""
        dialog = GameDetailDialog(self.app, game['id'])
    
    def download_game(self, game):
        """Start game download (P2)"""
        # Show download progress dialog
        from gui.download_dialog import DownloadProgressDialog
        dialog = DownloadProgressDialog(self.app, game)


class GameDetailDialog(ctk.CTkToplevel):
    """Game detail dialog (P1)"""
    
    def __init__(self, app, game_id):
        super().__init__(app)
        self.app = app
        self.game_id = game_id
        
        self.title("Game Details")
        self.geometry("700x600")
        
        # Make modal - delay grab_set until window is ready
        self.transient(app)
        self.update_idletasks()  # Ensure window is viewable
        self.after(10, self.grab_set)  # Delay grab to avoid race condition
        
        # Load details
        self.load_details()
    
    def load_details(self):
        """Load game details"""
        loading = ctk.CTkLabel(self, text="Loading details...")
        loading.pack(expand=True)
        
        def load_thread():
            details = self.app.network.get_game_detail(self.game_id)
            reviews = self.app.network.get_reviews(self.game_id)
            self.after(0, lambda: self.display_details(details, reviews))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def display_details(self, details, reviews):
        """Display game details"""
        # Clear loading
        for widget in self.winfo_children():
            widget.destroy()
        
        if not details:
            error = ctk.CTkLabel(self, text="Failed to load details")
            error.pack(expand=True)
            return
        
        game = details['game']
        
        # Scrollable content
        content = ctk.CTkScrollableFrame(self)
        content.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        header = ctk.CTkFrame(content)
        header.pack(fill="x", pady=10)
        
        title = ctk.CTkLabel(
            header,
            text=game['name'],
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(anchor="w", padx=10, pady=5)
        
        meta = f"Version: {game['version']} | "
        meta += f"⭐ {game['rating']:.1f}/5.0 ({game['rating_count']} reviews)\n"
        meta += f"Players: {game['min_players']}-{game['max_players']} | "
        meta += f"Type: {game['type'].upper()} | "
        meta += f"Downloads: {game['downloads']}"
        
        meta_label = ctk.CTkLabel(header, text=meta, justify="left")
        meta_label.pack(anchor="w", padx=10)
        
        # Description
        desc_frame = ctk.CTkFrame(content)
        desc_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            desc_frame,
            text="Description:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkLabel(
            desc_frame,
            text=game['description'] or "No description available",
            wraplength=650,
            justify="left"
        ).pack(anchor="w", padx=10, pady=5)
        
        # Reviews section (P4)
        reviews_frame = ctk.CTkFrame(content)
        reviews_frame.pack(fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(
            reviews_frame,
            text=f"Reviews ({len(reviews)}):",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=5)
        
        if reviews:
            for review in reviews[:5]:  # Show first 5
                review_card = ctk.CTkFrame(reviews_frame)
                review_card.pack(fill="x", padx=10, pady=3)
                
                # Stars
                stars = "⭐" * review['rating'] + "☆" * (5 - review['rating'])
                review_header = f"{stars} - {review['username']}"
                
                ctk.CTkLabel(
                    review_card,
                    text=review_header,
                    font=ctk.CTkFont(size=12, weight="bold")
                ).pack(anchor="w", padx=10, pady=2)
                
                if review['comment']:
                    ctk.CTkLabel(
                        review_card,
                        text=review['comment'],
                        wraplength=600,
                        justify="left"
                    ).pack(anchor="w", padx=10, pady=2)
        else:
            ctk.CTkLabel(
                reviews_frame,
                text="No reviews yet. Be the first to review!",
                text_color="gray"
            ).pack(padx=10, pady=10)
        
        # Action buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        download_btn = ctk.CTkButton(
            btn_frame,
            text="⬇️ Download",
            fg_color="green",
            command=lambda: self.download_game(game)
        )
        download_btn.pack(side="left", padx=5)
        
        review_btn = ctk.CTkButton(
            btn_frame,
            text="✍️ Write Review",
            command=lambda: self.write_review(game)
        )
        review_btn.pack(side="left", padx=5)
        
        close_btn = ctk.CTkButton(
            btn_frame,
            text="Close",
            command=self.destroy
        )
        close_btn.pack(side="right", padx=5)
    
    def download_game(self, game):
        """Download game"""
        from gui.download_dialog import DownloadProgressDialog
        dialog = DownloadProgressDialog(self.app, game)
        self.destroy()
    
    def write_review(self, game):
        """Open review dialog (P4)"""
        from gui.review_dialog import ReviewDialog
        ReviewDialog(self.app, game['id'])