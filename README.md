# boomer-port

A port of [boomer](https://github.com/tsoding/boomer) to Python + GTK4, targeting Ubuntu GNOME 46.

The original boomer is a screen zoomer written in Nim using raw X11/GLX. This port replaces that with PyGObject (GTK4) for windowing and input, and OpenGL ES 3.2 via `Gtk.GLArea` for rendering — making it compatible with both X11 and Wayland GNOME sessions.

## Dependencies

```bash
sudo apt install \
  python3-gi gir1.2-gtk-4.0 \
  libgirepository-2.0-dev libcairo2-dev \
  python3-dbus
```

Then install Python packages into the project's virtual environment:

```bash
pip install PyGObject PyOpenGL numpy Pillow
```

## Quick Start

```bash
python src/boomer.py
```

This takes a screenshot of your current screen and opens it fullscreen so you can zoom and pan around it.

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

## Command-line Options

```
usage: boomer [-h] [-d seconds] [-w] [-c filepath] [--new-config [filepath]]

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
