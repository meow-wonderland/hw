"""
Review Dialog (P4)
"""
import customtkinter as ctk
import threading


class ReviewDialog(ctk.CTkToplevel):
    """Write review dialog"""
    
    def __init__(self, app, game_id):
        super().__init__(app)
        self.app = app
        self.game_id = game_id
        
        self.title("Write Review")
        self.geometry("500x500")  # 增加高度
        self.minsize(500, 500)    # 設置最小尺寸
        
        # Build UI first
        self.build_ui()
        
        # Make modal - after UI is built
        self.transient(app)
        self.update_idletasks()
        self.after(10, self.grab_set)
    
    def build_ui(self):
        """Build UI"""
        # Main container with padding
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title = ctk.CTkLabel(
            main_frame,
            text="✍️ Write a Review",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=(0, 20))
        
        # Rating section
        rating_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        rating_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            rating_frame,
            text="Rating:",
            font=ctk.CTkFont(size=14)
        ).pack(pady=5)
        
        # Star buttons
        self.rating = 0
        self.star_frame = ctk.CTkFrame(rating_frame, fg_color="transparent")
        self.star_frame.pack(pady=10)
        
        self.star_buttons = []
        for i in range(5):
            btn = ctk.CTkButton(
                self.star_frame,
                text="☆",
                width=50,
                font=ctk.CTkFont(size=24),
                command=lambda r=i+1: self.set_rating(r),
                fg_color=("gray70", "gray30"),
                hover_color=("gray60", "gray40")
            )
            btn.pack(side="left", padx=5)
            self.star_buttons.append(btn)
        
        self.rating_label = ctk.CTkLabel(
            rating_frame,
            text="No rating selected",
            font=ctk.CTkFont(size=12)
        )
        self.rating_label.pack(pady=5)
        
        # Comment section
        comment_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        comment_frame.pack(fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(
            comment_frame,
            text="Comment (optional):",
            font=ctk.CTkFont(size=14)
        ).pack(pady=(0, 5), anchor="w")
        
        self.comment_text = ctk.CTkTextbox(
            comment_frame,
            width=450,
            height=120,
            wrap="word"
        )
        self.comment_text.pack(fill="both", expand=True)
        
        # Status label (above buttons)
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(pady=10)
        
        # Buttons frame (fixed at bottom)
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 0))
        
        submit_btn = ctk.CTkButton(
            btn_frame,
            text="✅ Submit Review",
            command=self.submit_review,
            fg_color="green",
            hover_color="#006400",
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        submit_btn.pack(side="left", padx=10)
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="❌ Cancel",
            command=self.destroy,
            fg_color=("gray60", "gray40"),
            hover_color=("gray50", "gray30"),
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        cancel_btn.pack(side="left", padx=10)
    
    def set_rating(self, rating):
        """Set star rating"""
        self.rating = rating
        self.rating_label.configure(text=f"Rating: {rating}/5 ⭐")
        
        # Update star display
        for i, btn in enumerate(self.star_buttons):
            if i < rating:
                btn.configure(
                    text="⭐",
                    fg_color="gold",
                    hover_color="orange"
                )
            else:
                btn.configure(
                    text="☆",
                    fg_color=("gray70", "gray30"),
                    hover_color=("gray60", "gray40")
                )
    
    def submit_review(self):
        """Submit review"""
        if self.rating == 0:
            self.status_label.configure(
                text="❌ Please select a rating",
                text_color="red"
            )
            return
        
        comment = self.comment_text.get("1.0", "end-1c").strip()
        
        self.status_label.configure(
            text="⏳ Submitting review...",
            text_color="yellow"
        )
        
        def submit_thread():
            success, message = self.app.network.submit_review(
                self.game_id,
                self.rating,
                comment
            )
            self.after(0, lambda: self.on_submit_result(success, message))
        
        threading.Thread(target=submit_thread, daemon=True).start()
    
    def on_submit_result(self, success, message):
        """Handle submit result"""
        if success:
            self.status_label.configure(
                text="✅ Review submitted!",
                text_color="green"
            )
            self.after(1500, self.destroy)
            self.after(2000, lambda: self.app.show_info(
                "✅ Thank you for your review!"
            ))
        else:
            self.status_label.configure(
                text=f"❌ {message}",
                text_color="red"
            )