# PokeMMO Overlay - Macro System

Windows overlay for PokeMMO that records keyboard and mouse macros and replays them relative to the game window, with Auto Hunt and Sweet Scent helpers.

## Features

- **Record and replay** keyboard and mouse input, with recorded timing between events
- **Game window detection**: finds the window whose title contains `PokeMMO` and shows its status in the overlay
- **Relative coordinates**: macro positions are stored relative to the game window, so they follow it when it moves or resizes
- **Macro categories**: General, Movement, Battles, Inventory, Trading, Custom
- **Loop playback** with a stop hotkey (F12)
- **Emergency stop**: ESC or P halts a running macro
- **Macro management**: Play, Edit, Duplicate, Export, and Delete from the right-click menu
- **Auto Hunt tab**: battle-menu detection using template images, with optional OCR (Tesseract)
- **Sweet Scent tab**: encounter loop driven by JSON presets
- **Fishing tab**: placeholder only, not implemented

## Requirements

- Windows 10/11 (the code uses the Win32 API through `pywin32`)
- Python 3
- PokeMMO
- Tesseract OCR, only if you want OCR-based detection in Auto Hunt. It is searched for in the default Windows install paths.

## Run it

```bash
pip install -r requirements.txt
python main.py
```

`requirements.txt` installs `pywin32`, `opencv-python`, `pillow`, `numpy`, and `pytesseract`.

## Usage

### Record a macro

1. Start PokeMMO.
2. Press `` ` `` (or click **Record** in the overlay) to start recording.
3. Perform the actions in PokeMMO.
4. Press `` ` `` again to stop, then click **Save**, enter a name, and choose a category.

### Play a macro

1. Select a macro in the list and double-click it, or click **Play**.
2. Keep the PokeMMO window focused while the macro runs.
3. Press ESC or P to stop.

### Hotkeys

| Key | Action |
|---|---|
| `` ` `` | Toggle recording (`TOGGLE_RECORDING_KEY` in `config.py`) |
| F12 | Stop loop playback (`STOP_LOOP_KEY`) |
| ESC or P | Emergency stop |

Macros are stored as JSON under `macros/<category>/`. Examples are included in `macros/`.

## Configuration

Edit `config.py` to change:

- Overlay size, opacity, and always-on-top
- Game window title (`GAME_WINDOW_TITLE`, default `PokeMMO`)
- Recording limits and thresholds (`MAX_RECORDING_TIME`, `MOUSE_MOVE_THRESHOLD`, `RECORDING_PRECISION`)
- Playback speed and delay between actions
- OCR screenshot interval
- Hotkeys and macro categories

### Auto Hunt battle-menu templates

Auto Hunt detects the battle menu by template matching. To set it up:

1. Take a screenshot of the battle menu during an encounter.
2. Save it as a PNG in `templates/`. `templates/README.txt` has the details.
3. Click **Load Templates** in the Auto Hunt tab.

Auto Hunt presets live in `auto_hunt_presets/`, and Sweet Scent presets live in `sweet_scent_presets/`.

## Advanced usage

- Macros are plain JSON files. You can edit timing, coordinates, or actions by hand.
- Export a macro from the right-click menu to share it. `macro_manager.py` also has an `import_macro` function, but the overlay has no import button.
- Keep a backup of your `macros/` folder.

## Troubleshooting

**"Game: Not Found"**
- Make sure PokeMMO is running.
- Check that the window title contains `PokeMMO`.
- Restart the overlay.

**Macro does not play**
- Make sure the PokeMMO window is active and focused.
- Check that the macro file exists and is valid JSON.
- Make sure no other macro is running.

**Recording or input does not work**
- Try running as Administrator.
- Check that antivirus is not blocking input simulation.
- Make sure no other macro or input tool is interfering.

**OCR does not work in Auto Hunt**
- Install Tesseract OCR to a default location, or set the path in `auto_hunt.py`.

## Project structure

```
main.py              # Entry point and main UI
overlay.py           # Overlay window and macro list
macro_manager.py     # Macro load, save, duplicate, export, import
input_manager.py     # Input recording and playback
window_manager.py    # PokeMMO window detection
auto_hunt.py         # Auto Hunt engine (template and OCR detection)
auto_hunt_pp.py      # Auto Hunt variant with PP management
sweet_scent.py       # Sweet Scent engine
config.py            # Settings
macros/              # Macro JSON files by category
templates/           # Battle-menu template images
sprites/             # Sprite images
auto_hunt_presets/   # Auto Hunt presets
sweet_scent_presets/ # Sweet Scent presets
debug_screenshots/   # Screenshots written by Auto Hunt
```

## Important: game terms and account risk

This tool automates game input. Automating PokeMMO may go against the game's terms of service, and the game operator may take action against accounts that use it. The project makes no guarantee that using it is safe for your account. Use it at your own risk, and follow the game's rules and community guidelines.

## License

This project is for educational purposes only. Use responsibly and in accordance with game terms of service.
