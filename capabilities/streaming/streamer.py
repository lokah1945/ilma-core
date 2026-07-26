"""Streaming module with real-time updates."""
import sys
import time
from datetime import datetime

class ILMAStreamer:
    LABELS = {
        "thinking": "🧠 BERPIKIR",
        "planning": "📋 MENGURAI",
        "searching": "🔍 MENELITI",
        "working": "⚙️ MENERAPKAN",
        "verifying": "✅ MEMVERIFIKASI",
        "done": "✨ SELESAI"
    }
    
    def __init__(self, prefix=""):
        self.prefix = prefix
    
    def stream(self, label: str, message: str, persist: bool = False):
        """Stream a message with timestamp and label."""
        now = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{self.LABELS.get(label, label)}] [{now}] {message}"
        
        if persist:
            print(full_msg)
        else:
            print(f"\r{full_msg}", end="", flush=True)
    
    def done(self, message: str):
        """Mark as done."""
        print(f"\n[{self.LABELS['done']}] [{datetime.now().strftime('%H:%M:%S')}] {message}")

def stream(label: str, message: str):
    """Quick stream function."""
    streamer = ILMAStreamer()
    streamer.stream(label, message)
