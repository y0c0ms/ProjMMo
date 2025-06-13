"""
Window Manager for detecting and tracking PokeMMO game window
"""
import win32gui
import win32con
import threading
import time
from config import GAME_WINDOW_TITLE, DETECTION_INTERVAL

class WindowManager:
    def __init__(self):
        self.game_hwnd = None
        self.game_rect = None
        self.is_monitoring = False
        self.monitor_thread = None
        self.callbacks = []
        
    def find_game_window(self):
        """Find PokeMMO window handle"""
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if GAME_WINDOW_TITLE.lower() in window_title.lower():
                    windows.append((hwnd, window_title))
            return True
        
        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        
        if windows:
            # Take the first matching window
            self.game_hwnd = windows[0][0]
            self.update_game_rect()
            return True
        
        self.game_hwnd = None
        self.game_rect = None
        return False
    
    def update_game_rect(self):
        """Update game window rectangle"""
        if self.game_hwnd:
            try:
                self.game_rect = win32gui.GetWindowRect(self.game_hwnd)
                return True
            except:
                self.game_hwnd = None
                self.game_rect = None
                return False
        return False
    
    def is_game_active(self):
        """Check if PokeMMO window is active/focused"""
        if not self.game_hwnd:
            # Try to find the game window if we don't have it
            self.find_game_window()
            if not self.game_hwnd:
                return False
        
        try:
            foreground_hwnd = win32gui.GetForegroundWindow()
            # Also check if the window is still valid
            if not win32gui.IsWindow(self.game_hwnd):
                # Window handle is invalid, try to find it again
                self.find_game_window()
                if not self.game_hwnd:
                    return False
                foreground_hwnd = win32gui.GetForegroundWindow()
            
            return foreground_hwnd == self.game_hwnd
        except:
            # If there's an error, try to re-find the window
            self.find_game_window()
            return False
    
    def is_game_running(self):
        """Check if PokeMMO is still running"""
        if not self.game_hwnd:
            return False
        
        try:
            return win32gui.IsWindow(self.game_hwnd)
        except:
            return False
    
    def get_game_position(self):
        """Get game window position and size"""
        if self.game_rect:
            x, y, right, bottom = self.game_rect
            return {
                'x': x,
                'y': y, 
                'width': right - x,
                'height': bottom - y
            }
        return None
    
    def screen_to_game_coords(self, screen_x, screen_y):
        """Convert screen coordinates to game window relative coordinates"""
        if not self.game_rect:
            return screen_x, screen_y
        
        game_x = screen_x - self.game_rect[0]
        game_y = screen_y - self.game_rect[1]
        return game_x, game_y
    
    def game_to_screen_coords(self, game_x, game_y):
        """Convert game window relative coordinates to screen coordinates"""
        if not self.game_rect:
            return game_x, game_y
        
        screen_x = game_x + self.game_rect[0]
        screen_y = game_y + self.game_rect[1]
        return screen_x, screen_y
    
    def add_callback(self, callback):
        """Add callback for window events"""
        self.callbacks.append(callback)
    
    def start_monitoring(self):
        """Start monitoring game window"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring game window"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
    
    def _monitor_loop(self):
        """Monitor loop for tracking window changes"""
        while self.is_monitoring:
            old_rect = self.game_rect
            
            # Try to find game if not found
            if not self.game_hwnd:
                self.find_game_window()
            
            # Update rect if game exists
            if self.game_hwnd:
                self.update_game_rect()
            
            # Check if window moved/resized
            if old_rect != self.game_rect:
                for callback in self.callbacks:
                    try:
                        callback('window_changed', self.get_game_position())
                    except:
                        pass
            
            time.sleep(DETECTION_INTERVAL) 