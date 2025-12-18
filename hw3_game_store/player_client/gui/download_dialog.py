"""
Download Progress Dialog (P2)
"""
import customtkinter as ctk
import threading


class DownloadProgressDialog(ctk.CTkToplevel):
    """Download progress window"""
    
    def __init__(self, app, game):
        super().__init__(app)
        self.app = app
        self.game = game
        
        self.title(f"Downloading {game['name']}")
        self.geometry("500x250")
        
        # Build UI first
        self.build_ui()
        
        # Make modal - after UI is built
        self.transient(app)
        self.update_idletasks()
        self.after(10, self.grab_set)
        
        self.start_download()
    
    def build_ui(self):
        """Build UI"""
        # Title
        title = ctk.CTkLabel(
            self,
            text=f"Downloading: {self.game['name']}",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(pady=20)
        
        # Progress bar
        self.progress = ctk.CTkProgressBar(self, width=400)
        self.progress.pack(pady=10)
        self.progress.set(0)
        
        # Status label
        self.status_label = ctk.CTkLabel(self, text="Starting download...")
        self.status_label.pack(pady=5)
        
        # Percentage label
        self.percent_label = ctk.CTkLabel(
            self,
            text="0%",
            font=ctk.CTkFont(size=24)
        )
        self.percent_label.pack(pady=10)
        
        # Speed label
        self.speed_label = ctk.CTkLabel(self, text="")
        self.speed_label.pack(pady=5)
    
    def start_download(self):
        """Start downloading"""
        import time
        self.start_time = time.time()
        self.last_update = time.time()
        self.last_received = 0
        
        def download_thread():
            self.app.download_manager.download_game(
                game_id=self.game['id'],
                version=self.game.get('version'),
                progress_callback=self.on_progress,
                complete_callback=self.on_complete
            )
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def on_progress(self, received: int, total: int):
        """Update progress"""
        percent = received / total if total > 0 else 0
        
        self.after(0, lambda: self.progress.set(percent))
        self.after(0, lambda: self.percent_label.configure(text=f"{percent*100:.1f}%"))
        self.after(0, lambda: self.status_label.configure(
            text=f"{received//1024} KB / {total//1024} KB"
        ))
        
        # Calculate speed
        import time
        now = time.time()
        if now - self.last_update >= 0.5:  # Update every 0.5s
            speed = (received - self.last_received) / (now - self.last_update) / 1024
            self.after(0, lambda: self.speed_label.configure(text=f"{speed:.1f} KB/s"))
            self.last_update = now
            self.last_received = received
    
    def on_complete(self, success: bool, message: str):
        """Download complete"""
        if success:
            self.after(0, lambda: self.status_label.configure(
                text="✓ Download complete!"
            ))
            self.after(0, lambda: self.percent_label.configure(text="100%"))
            self.after(2000, self.destroy)
            
            self.after(2500, lambda: self.app.show_info(
                f"✓ {self.game['name']} downloaded successfully!\n\n"
                f"You can now play it from the Lobby."
            ))
        else:
            self.after(0, lambda: self.status_label.configure(
                text=f"✗ Download failed: {message}"
            ))
            self.after(0, lambda: self.percent_label.configure(text="Failed"))