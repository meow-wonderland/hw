"""
Game Store Player Client - Main GUI Application
Uses CustomTkinter for modern UI
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import customtkinter as ctk
except ImportError:
    print("Installing customtkinter...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

import logging
import threading

import config
from client.network_client import NetworkClient
from client.download_manager import DownloadManager
from protocol import Message, MessageType

# Set appearance
ctk.set_appearance_mode(config.THEME)
ctk.set_default_color_theme(config.COLOR_THEME)

logger = logging.getLogger(__name__)


class GameStoreApp(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self.title("🎮 Game Store - Player Client")
        self.geometry("1200x800")
        
        # Network
        self.network = NetworkClient(on_message_callback=self.on_server_message)
        self.download_manager = None  # Will be initialized after login
        
        # State
        self.current_user = None
        self.current_view = None
        self.current_room = None
        
        # Build UI
        self.build_ui()
        
        # Auto-connect (will show login if not connected)
        self.after(100, self.show_login)
    
    def build_ui(self):
        """Build main UI structure"""
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)
        
        # Logo
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="🎮 Game Store",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.logo_label.pack(pady=30, padx=20)
        
        # Username display
        self.username_label = ctk.CTkLabel(
            self.sidebar,
            text="Not logged in",
            font=ctk.CTkFont(size=12)
        )
        self.username_label.pack(pady=10, padx=20)
        
        # Current room status (initially hidden)
        self.room_status_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color="darkgreen",
            corner_radius=8
        )
        
        self.room_status_label = ctk.CTkLabel(
            self.room_status_frame,
            text="🎮 In Room",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white"
        )
        self.room_status_label.pack(pady=5, padx=10)
        
        self.return_room_btn = ctk.CTkButton(
            self.room_status_frame,
            text="↩ Return to Room",
            command=self.return_to_room,
            height=30,
            font=ctk.CTkFont(size=11),
            fg_color="green"
        )
        self.return_room_btn.pack(pady=5, padx=10, fill="x")
        
        # Navigation buttons
        self.nav_buttons = {}
        
        nav_items = [
            ("📦 Store", self.show_store),
            ("💾 My Games", self.show_my_games),
            ("🎲 Lobby", self.show_lobby),
            ("🔌 Plugins", self.show_plugins),
        ]
        
        for text, command in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                command=command,
                height=40,
                font=ctk.CTkFont(size=14)
            )
            btn.pack(pady=10, padx=20, fill="x")
            self.nav_buttons[text] = btn
        
        # Spacer
        ctk.CTkLabel(self.sidebar, text="").pack(expand=True)
        
        # Logout button
        self.logout_btn = ctk.CTkButton(
            self.sidebar,
            text="🚪 Logout",
            command=self.logout,
            height=40,
            fg_color="darkred"
        )
        self.logout_btn.pack(side="bottom", pady=20, padx=20, fill="x")
        
        # Main content area
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        # Status bar
        self.status_frame = ctk.CTkFrame(self, height=30)
        self.status_frame.pack(side="bottom", fill="x", padx=10, pady=5)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="● Not connected",
            anchor="w"
        )
        self.status_label.pack(side="left", padx=10)
    
    def show_login(self):
        """Show login dialog"""
        if self.network.connected and self.current_user:
            self.show_store()
            return
        
        dialog = LoginDialog(self)
        self.wait_window(dialog)
        
        if self.current_user:
            self.username_label.configure(text=f"👤 {self.current_user}")
            self.status_label.configure(text="● Connected", text_color="green")
            self.show_store()
    
    def logout(self):
        """Logout and disconnect"""
        # Leave room if currently in one
        if self.current_room:
            room_id = self.current_room.get('room_id') or self.current_room.get('id')
            if room_id:
                self.network.leave_room(room_id)
            self.current_room = None
        
        self.network.disconnect()
        self.current_user = None
        self.username_label.configure(text="Not logged in")
        self.status_label.configure(text="● Disconnected", text_color="red")
        self.show_login()
    
    def clear_main_frame(self):
        """Clear main content area"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
    
    def show_store(self):
        """P1: Show game store view"""
        self.clear_main_frame()
        from gui.store_view import StoreView
        self.current_view = StoreView(self.main_frame, self)
        self.current_view.pack(fill="both", expand=True)
    
    def show_my_games(self):
        """P2: Show downloaded games"""
        self.clear_main_frame()
        from gui.my_games_view import MyGamesView
        self.current_view = MyGamesView(self.main_frame, self)
        self.current_view.pack(fill="both", expand=True)
    
    def show_lobby(self):
        """P3: Show game lobby"""
        self.clear_main_frame()
        # Don't clear current_room here - user might just be browsing
        # Hide room status if showing lobby
        self.room_status_frame.pack_forget()
        
        from gui.lobby_view import LobbyView
        self.current_view = LobbyView(self.main_frame, self)
        self.current_view.pack(fill="both", expand=True)
    
    def show_room_view(self, room_data: dict):
        """P3: Show room waiting view"""
        self.clear_main_frame()
        self.current_room = room_data
        
        # Show room status in sidebar
        self.room_status_frame.pack(pady=10, padx=20, fill="x", after=self.username_label)
        
        from gui.room_view import RoomView
        self.current_view = RoomView(self.main_frame, self, room_data)
        self.current_view.pack(fill="both", expand=True)
    
    def return_to_room(self):
        """Return to current room view"""
        if self.current_room:
            self.show_room_view(self.current_room)
        else:
            self.show_lobby()
    
    def show_view(self, view_name: str):
        """Show a named view"""
        if view_name == 'store':
            self.show_store()
        elif view_name == 'my_games':
            self.show_my_games()
        elif view_name == 'lobby':
            self.show_lobby()
        elif view_name == 'plugins':
            self.show_plugins()
    
    def show_plugins(self):
        """Show plugins view"""
        self.clear_main_frame()
        label = ctk.CTkLabel(
            self.main_frame,
            text="🔌 Plugin System\n\nComing soon...",
            font=ctk.CTkFont(size=20)
        )
        label.pack(expand=True)
    
    def on_server_message(self, message: Message):
        """Handle unsolicited server messages"""
        if message.msg_type == MessageType.GAME_STARTED:
            # Game server started notification
            self.show_game_started_dialog(message.payload)
        elif message.msg_type == MessageType.ROOM_UPDATE:
            # Room update notification
            try:
                if hasattr(self.current_view, 'on_room_update'):
                    self.current_view.on_room_update(message.payload)
            except Exception as e:
                # View might be destroyed or transitioning - ignore
                logger.debug(f"Ignoring room update (view transitioning): {e}")
    
    def show_game_started_dialog(self, data: dict):
        """Show dialog when game starts"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Game Started!")
        dialog.geometry("400x200")
        
        label = ctk.CTkLabel(
            dialog,
            text=f"🎮 {data['game_name']} is starting!\n\n"
                 f"Game server: linux1.cs.nycu.edu.tw:{data['game_port']}\n\n"
                 f"Launching game client...",
            font=ctk.CTkFont(size=14)
        )
        label.pack(expand=True, pady=20)
        
        # Auto-launch game client
        self.after(2000, lambda: self.launch_game_client(data))
        self.after(3000, dialog.destroy)
    
    def launch_game_client(self, data: dict):
        """Launch game client process (P3)"""
        game_name = data['game_name']
        game_port = data['game_port']
        
        # Find game in per-player downloads directory
        game_path = Path(config.DOWNLOADS_DIR) / self.current_user / game_name / "current"
        
        if not game_path.exists():
            self.show_error(f"Game not found: {game_name}\nPlease download it first.")
            return
        
        # Launch game client
        import subprocess
        client_script = game_path / "game_client.py"
        
        if not client_script.exists():
            self.show_error(f"Game client not found: {client_script}")
            return
        
        try:
            subprocess.Popen([
                sys.executable,
                str(client_script),
                '--server', 'linux1.cs.nycu.edu.tw',
                '--port', str(game_port),
                '--username', self.current_user
            ], cwd=str(game_path))
            
            logger.info(f"Launched game client for {game_name}")
            self.show_info(f"Game client launched!\nConnecting to port {game_port}")
            
        except Exception as e:
            self.show_error(f"Failed to launch game: {e}")
    
    def show_error(self, message: str):
        """Show error dialog"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Error")
        dialog.geometry("400x200")
        
        label = ctk.CTkLabel(dialog, text=f"❌ {message}", wraplength=350)
        label.pack(expand=True, pady=20)
        
        btn = ctk.CTkButton(dialog, text="OK", command=dialog.destroy)
        btn.pack(pady=10)
    
    def show_info(self, message: str):
        """Show info dialog"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Info")
        dialog.geometry("400x150")
        
        label = ctk.CTkLabel(dialog, text=message, wraplength=350)
        label.pack(expand=True, pady=20)
        
        btn = ctk.CTkButton(dialog, text="OK", command=dialog.destroy)
        btn.pack(pady=10)


class LoginDialog(ctk.CTkToplevel):
    """Login/Register dialog"""
    
    def __init__(self, parent: GameStoreApp):
        super().__init__(parent)
        self.parent = parent
        
        self.title("Login to Game Store")
        self.geometry("400x300")
        self.resizable(False, False)
        
        # Build UI first
        self.build_ui()
        
        # Make modal - after UI is built
        self.transient(parent)
        self.update_idletasks()
        self.after(10, self.grab_set)
        
        # Try to connect
        self.after(100, self.try_connect)
    
    def build_ui(self):
        """Build login UI"""
        # Title
        title = ctk.CTkLabel(
            self,
            text="🎮 Game Store Login",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        # Username
        ctk.CTkLabel(self, text="Username:").pack(pady=5)
        self.username_entry = ctk.CTkEntry(self, width=250)
        self.username_entry.pack(pady=5)
        
        # Password
        ctk.CTkLabel(self, text="Password:").pack(pady=5)
        self.password_entry = ctk.CTkEntry(self, width=250, show="*")
        self.password_entry.pack(pady=5)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        self.login_btn = ctk.CTkButton(
            btn_frame,
            text="Login",
            command=self.do_login,
            width=120
        )
        self.login_btn.pack(side="left", padx=10)
        
        self.register_btn = ctk.CTkButton(
            btn_frame,
            text="Register",
            command=self.do_register,
            width=120
        )
        self.register_btn.pack(side="left", padx=10)
        
        # Status
        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.pack(pady=10)
    
    def try_connect(self):
        """Try to connect to server"""
        self.status_label.configure(text="Connecting to server...")
        
        def connect_thread():
            success = self.parent.network.connect(config.SERVER_HOST, config.LOBBY_PORT)
            self.after(0, lambda: self.on_connect_result(success))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def on_connect_result(self, success: bool):
        """Handle connection result"""
        if success:
            self.status_label.configure(text="✓ Connected to server", text_color="green")
        else:
            self.status_label.configure(text="✗ Connection failed", text_color="red")
    
    def do_login(self):
        """Perform login"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            self.status_label.configure(text="Please enter username and password", text_color="red")
            return
        
        self.status_label.configure(text="Logging in...")
        self.login_btn.configure(state="disabled")
        
        def login_thread():
            success, message, logged_in_username = self.parent.network.login(username, password)
            self.after(0, lambda: self.on_login_result(success, message, logged_in_username))
        
        threading.Thread(target=login_thread, daemon=True).start()
    
    def on_login_result(self, success: bool, message: str, username: str):
        """Handle login result"""
        self.login_btn.configure(state="normal")
        
        if success:
            self.parent.current_user = username
            
            # Initialize download manager with username
            from client.download_manager import DownloadManager
            self.parent.download_manager = DownloadManager(username, self.parent.network)
            logger.info(f"Download manager initialized for user: {username}")
            
            self.destroy()
        else:
            self.status_label.configure(text=f"✗ {message}", text_color="red")
    
    def do_register(self):
        """Perform registration"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            self.status_label.configure(text="Please enter username and password", text_color="red")
            return
        
        self.status_label.configure(text="Registering...")
        self.register_btn.configure(state="disabled")
        
        def register_thread():
            success, message = self.parent.network.register(username, password)
            self.after(0, lambda: self.on_register_result(success, message))
        
        threading.Thread(target=register_thread, daemon=True).start()
    
    def on_register_result(self, success: bool, message: str):
        """Handle registration result"""
        self.register_btn.configure(state="normal")
        
        if success:
            self.status_label.configure(text=f"✓ {message} - Please login", text_color="green")
        else:
            self.status_label.configure(text=f"✗ {message}", text_color="red")


def main():
    """Main entry point"""
    logging.basicConfig(
        level=logging.INFO if config.DEBUG else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    app = GameStoreApp()
    app.mainloop()


if __name__ == '__main__':
    main()