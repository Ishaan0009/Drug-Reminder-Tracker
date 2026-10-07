# ui_manager.py
# handles theme values, apply_theme function and settings panel UI
import tkinter as tk
from tkinter import ttk

# Theme definitions (red main)
DARK = {
    "bg": "#0f1115",
    "card": "#15161a",
    "entry_bg": "#222429",   # light-ish entry bg in dark mode
    "entry_fg": "#E0E0E0",   # requested soft light gray
    "text": "#E0E0E0",
    "sub": "#9aa3ad",
    "accent": "#b91d73",     # purple accent for toggle circle
    "accent_primary": "#e53935",  # red primary for general buttons
    "progress": "#e53935",
}

LIGHT = {
    "bg": "#f3f5f7",
    "card": "#ffffff",
    "entry_bg": "#ffffff",
    "entry_fg": "#111111",
    "text": "#111827",
    "sub": "#6b7280",
    "accent": "#7c3aed",      # purple accent (lighter)
    "accent_primary": "#dc2626",
    "progress": "#9b59b6",
}

# fonts list exposed to user
FONTS = ["Segoe UI", "Roboto", "Poppins"]

class UIManager:
    def __init__(self):
        self.dark_mode = True
        self.theme = DARK.copy()

    def toggle_mode_immediate(self):
        """Flip mode instantly and update theme dict"""
        self.dark_mode = not self.dark_mode
        self.theme = DARK.copy() if self.dark_mode else LIGHT.copy()

    def get_theme(self):
        return self.theme

    def get_fonts(self):
        return FONTS
