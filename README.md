# boomer

A port of [boomer](https://github.com/tsoding/boomer) to Python + GTK4, targeting Ubuntu GNOME 46.

The original boomer is a screen zoomer written in Nim using raw X11/GLX. This port replaces that with PyGObject (GTK4) for windowing and input, and OpenGL ES 3.2 via `Gtk.GLArea` for rendering — making it compatible with both X11 and Wayland GNOME sessions.

## Dependencies

```bash
sudo apt install \
  python3-gi gir1.2-gtk-3.0 gir1.2-gtk-4.0 \
  libgirepository-2.0-dev libcairo2-dev \
  python3-dbus
```

`gi` is provided by Ubuntu's `python3-gi` package. If you use a virtual environment, create it from the system Python with system packages enabled so PyGObject remains visible:

```bash
/usr/bin/python3 -m venv --system-site-packages .venv
source .venv/bin/activate
```

Then install the Python packages into that virtual environment:

```bash
pip install -r requirements.txt
```

If `python src/boomer.py` fails with `ModuleNotFoundError: No module named 'gi'`, the active Python cannot see the system PyGObject package. Recreate the virtual environment with `--system-site-packages` as shown above, or run Boomer with `/usr/bin/python3`.

For tray icon support on Ubuntu/GNOME, make sure AppIndicator support is available:

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

The tray launcher writes capture output and errors to `~/.cache/boomer/tray.log`.

## Quick Start

Run Boomer as a background tray app:

```bash
python src/tray.py
```

The tray menu lets you trigger a new capture, toggle windowed captures, open preferences, and quit the background process. Preferences are stored in `~/.config/boomer/tray_config`.

To start the tray process detached from your terminal:

```bash
nohup python src/tray.py >/tmp/boomer-tray.log 2>&1 &
```

The default tray hotkey is `Ctrl` + `Alt` + `Z`. Global hotkeys work on X11 through `pynput`; GNOME Wayland may block app-level global shortcuts.

For development, the direct capture window can still be launched with:

```bash
python src/boomer.py
```

After installing the Debian package, the only public launcher is `boomer`; it starts the tray app.

If you need a GNOME custom keyboard shortcut for Wayland, use the internal capture command:

```bash
/usr/bin/python3 /usr/lib/boomer/boomer.py
```

## Build a Debian Package

Build an installable `.deb` from the current source tree:

```bash
scripts/build-deb.sh
```

The package is written to `dist/`. Install it with apt so system dependencies are resolved automatically:

```bash
sudo apt install ./dist/boomer_0.1.2_all.deb
```

After installation, run Boomer with `boomer`; it starts the tray app in the background and returns immediately. Launcher output is written to `~/.cache/boomer/tray-launcher.log`.

## Controls

| Control | Description |
|---|---|
| Scroll wheel or `=` / `-` | Zoom in / out |
| Drag (left mouse button) | Pan the image |
| `0` | Reset zoom, position, and mirror |
| `f` | Toggle flashlight effect |
| `Ctrl` + Scroll (flashlight on) | Resize flashlight radius |
| `m` | Mirror the image horizontally |
| `r` | Reload config file |
| `q` or `Esc` | Quit |

## Tray Preferences

The background tray process stores its own preferences separately from the zoom physics config:

```ini
[tray]
shortcut = <ctrl>+<alt>+z
windowed = false
delay = 0.0
config_file = /home/you/.config/boomer/config
```

Use `Preferences...` from the tray menu to edit these values, or edit `~/.config/boomer/tray_config` directly.

## Internal Capture Options

The installed app is intentionally tray-only: users launch `boomer`, then trigger captures from the tray menu or shortcut. The direct capture script remains available internally for the tray launcher and for development.

```
usage: python src/boomer.py [-h] [-d seconds] [-w] [-c filepath] [--new-config [filepath]]

options:
  -d, --delay seconds     Delay start by N seconds (useful for capturing menus)
  -w, --windowed          Run in a window instead of fullscreen
  -c, --config filepath   Use a custom config file
      --new-config [path] Generate a default config file and exit
  -h, --help              Show this help message
```

## Configuration

The config file lives at `~/.config/boomer/config`. Generate a default one with:

```bash
python src/boomer.py --new-config
```

| Parameter | Default | Description |
|---|---|---|
| `min_scale` | `0.01` | Minimum zoom level |
| `scroll_speed` | `1.5` | Zoom speed per scroll tick |
| `drag_friction` | `6.0` | How fast panning momentum decays |
| `scale_friction` | `4.0` | How fast zoom momentum decays |

Example `~/.config/boomer/config`:

```
min_scale = 0.01
scroll_speed = 2.0
drag_friction = 8.0
scale_friction = 4.0
# this is a comment
```

## Screenshot Backend

The app tries screenshot methods in this order until one succeeds:

1. **GNOME Shell DBus** (`org.gnome.Shell.Screenshot`) — works on both X11 and Wayland GNOME sessions; requires `python3-dbus`
2. **grim** — Wayland-native compositor screenshot tool
3. **scrot** — X11 screenshot tool
4. **PIL ImageGrab** — fallback using Pillow

On a standard Ubuntu GNOME 46 install, the DBus method works out of the box.

## How it Differs from the Original

| | Original (Nim) | This port (Python) |
|---|---|---|
| Language | Nim | Python 3 |
| Windowing | Raw X11 | GTK4 (PyGObject) |
| Rendering | OpenGL 3.x + GLX | OpenGL ES 3.2 via `Gtk.GLArea` |
| Wayland | No | Yes (via GTK4) |
| Screenshot | `XGetImage` | GNOME Shell DBus / grim / scrot |
| Shaders | GLSL 1.30 | GLSL ES 3.20 |
