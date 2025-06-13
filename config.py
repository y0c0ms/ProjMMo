"""
Configuration settings for PokeMMO Overlay
"""

# UI Settings
OVERLAY_WIDTH = 300
OVERLAY_HEIGHT = 400
OVERLAY_OPACITY = 0.9
ALWAYS_ON_TOP = True

# Game Detection
GAME_WINDOW_TITLE = "PokeMMO"
DETECTION_INTERVAL = 1.0  # seconds

# Recording Settings
MAX_RECORDING_TIME = 300  # 5 minutes max
MOUSE_MOVE_THRESHOLD = 5  # pixels - minimum movement to record
RECORDING_PRECISION = 0.001  # seconds

# Playback Settings
DEFAULT_PLAYBACK_SPEED = 1.0
EMERGENCY_STOP_KEY = "esc"
SAFETY_DELAY = 0.1  # seconds between actions

# Hotkey Settings
STOP_RECORDING_KEY = "`"  # Default hotkey to stop recording
STOP_LOOP_KEY = "F12"  # Default hotkey to stop loop playback

# File Paths
MACROS_DIR = "macros"
CONFIG_FILE = "overlay_config.json"

# Macro Categories
MACRO_CATEGORIES = {
    "General": "General purpose macros",
    "Movement": "Movement and navigation",
    "Battles": "Combat and battle macros", 
    "Inventory": "Item and inventory management",
    "Trading": "Trading and market activities",
    "Custom": "Custom user macros"
}

# UI Colors
BG_COLOR = "#2b2b2b"
BUTTON_COLOR = "#3c3c3c"
TEXT_COLOR = "#ffffff"
ACCENT_COLOR = "#4a9eff"
RECORD_COLOR = "#ff4444" 