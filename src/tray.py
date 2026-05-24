#!/usr/bin/env python3
import configparser
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


APP_DIR = Path(__file__).resolve().parent
BOOMER_SCRIPT = APP_DIR / 'boomer.py'
CONFIG_DIR = Path.home() / '.config' / 'boomer'
CACHE_DIR = Path.home() / '.cache' / 'boomer'
TRAY_CONFIG_FILE = CONFIG_DIR / 'tray_config'
BOOMER_CONFIG_FILE = CONFIG_DIR / 'config'
TRAY_LOG_FILE = CACHE_DIR / 'tray.log'


@dataclass
class TrayConfig:
    shortcut: str = '<ctrl>+<alt>+z'
    windowed: bool = False
    delay: float = 0.0
    config_file: str = str(BOOMER_CONFIG_FILE)


class BoomerTray:
    def __init__(self):
        self.config = self._load_config()
        self.icon = None
        self.indicator = None
        self.gtk = None
        self.indicator_api = None
        self.backend = None
        self._hotkey_listener = None
        self._preferences_thread: Optional[threading.Thread] = None

    def run(self):
        self._setup_tray_backend()
        self._start_hotkey_listener()
        if self.backend == 'appindicator':
            self.gtk.main()
        else:
            self.icon.run()

    def _setup_tray_backend(self):
        if self._setup_appindicator():
            self.backend = 'appindicator'
            print('Using native AppIndicator tray backend')
            return
        self._setup_pystray()
        self.backend = 'pystray'
        print('Using pystray tray backend')

    def _setup_appindicator(self) -> bool:
        try:
            import gi
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk

            try:
                gi.require_version('AyatanaAppIndicator3', '0.1')
                from gi.repository import AyatanaAppIndicator3 as AppIndicator
            except (ImportError, ValueError):
                gi.require_version('AppIndicator3', '0.1')
                from gi.repository import AppIndicator3 as AppIndicator
        except Exception as error:
            print(f'Could not use native AppIndicator tray backend: {error}', file=sys.stderr)
            return False

        self.gtk = Gtk
        self.indicator_api = AppIndicator
        self.indicator = AppIndicator.Indicator.new(
            'boomer',
            'zoom-in-symbolic',
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._refresh_menu()
        return True

    def _setup_pystray(self):
        import pystray

        self.pystray = pystray
        self.icon = pystray.Icon(
            'boomer',
            self._create_icon(),
            'boomer',
            self._build_pystray_menu(),
        )

    def _refresh_menu(self):
        if self.backend == 'pystray' and self.icon:
            self.icon.menu = self._build_pystray_menu()
            self.icon.update_menu()
        elif self.indicator and self.gtk:
            self.indicator.set_menu(self._build_gtk_menu())

    def _build_pystray_menu(self):
        return self.pystray.Menu(
            self.pystray.MenuItem('Capture for Zoom', self.capture),
            self.pystray.MenuItem(
                'Windowed Capture',
                self._toggle_windowed,
                checked=lambda item: self.config.windowed,
            ),
            self.pystray.MenuItem(f'Shortcut: {self.config.shortcut}', None, enabled=False),
            self.pystray.MenuItem('Preferences...', self.open_preferences),
            self.pystray.MenuItem('Quit', self.quit),
        )

    def _build_gtk_menu(self):
        menu = self.gtk.Menu()

        capture_item = self.gtk.MenuItem(label='Capture for Zoom')
        capture_item.connect('activate', self.capture)
        menu.append(capture_item)

        windowed_item = self.gtk.CheckMenuItem(label='Windowed Capture')
        windowed_item.set_active(self.config.windowed)
        windowed_item.connect('toggled', self._set_windowed_from_menu)
        menu.append(windowed_item)

        shortcut_item = self.gtk.MenuItem(label=f'Shortcut: {self.config.shortcut}')
        shortcut_item.set_sensitive(False)
        menu.append(shortcut_item)

        preferences_item = self.gtk.MenuItem(label='Preferences...')
        preferences_item.connect('activate', self.open_preferences)
        menu.append(preferences_item)

        quit_item = self.gtk.MenuItem(label='Quit')
        quit_item.connect('activate', self.quit)
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _create_icon(self):
        from PIL import Image, ImageDraw

        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), fill=(36, 36, 36, 255))
        draw.ellipse((18, 18, 42, 42), outline=(255, 255, 255, 255), width=5)
        draw.line((40, 40, 53, 53), fill=(255, 255, 255, 255), width=6)
        return image

    def capture(self, icon=None, item=None):
        command = [
            sys.executable,
            str(BOOMER_SCRIPT),
            '--config',
            self.config.config_file,
        ]
        if self.config.windowed:
            command.append('--windowed')
        if self.config.delay > 0:
            command.extend(['--delay', str(self.config.delay)])

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(TRAY_LOG_FILE, 'a') as log_file:
            log_file.write(f'Launching: {" ".join(command)}\n')
            log_file.flush()

            stdout = log_file
            stderr = subprocess.STDOUT
            subprocess.Popen(
                command,
                cwd=str(APP_DIR.parent),
                start_new_session=True,
                stdout=stdout,
                stderr=stderr,
            )

    def capture_for_hotkey(self):
        self.capture()

    def _set_windowed_from_menu(self, menu_item):
        self.config.windowed = menu_item.get_active()
        self._save_config()

    def _toggle_windowed(self, icon=None, item=None):
        self.config.windowed = not self.config.windowed
        self._save_config()
        self._refresh_menu()

    def open_preferences(self, icon=None, item=None):
        if self._preferences_thread and self._preferences_thread.is_alive():
            return
        self._preferences_thread = threading.Thread(
            target=self._show_preferences,
            name='boomer-preferences',
            daemon=True,
        )
        self._preferences_thread.start()

    def quit(self, icon=None, item=None):
        self._stop_hotkey_listener()
        if self.backend == 'appindicator':
            self.gtk.main_quit()
        else:
            self.icon.stop()

    def _show_preferences(self):
        try:
            import tkinter as tk
            from tkinter import messagebox
        except Exception:
            self._open_config_file()
            return

        root = tk.Tk()
        root.title('Boomer Preferences')
        root.resizable(False, False)

        shortcut_value = tk.StringVar(value=self.config.shortcut)
        delay_value = tk.StringVar(value=str(self.config.delay))
        config_file_value = tk.StringVar(value=self.config.config_file)
        windowed_value = tk.BooleanVar(value=self.config.windowed)

        form = tk.Frame(root, padx=12, pady=12)
        form.grid(row=0, column=0, sticky='nsew')

        tk.Label(form, text='Shortcut').grid(row=0, column=0, sticky='w', pady=4)
        tk.Entry(form, width=36, textvariable=shortcut_value).grid(row=0, column=1, pady=4)

        tk.Label(form, text='Delay seconds').grid(row=1, column=0, sticky='w', pady=4)
        tk.Entry(form, width=36, textvariable=delay_value).grid(row=1, column=1, pady=4)

        tk.Label(form, text='Config file').grid(row=2, column=0, sticky='w', pady=4)
        tk.Entry(form, width=36, textvariable=config_file_value).grid(row=2, column=1, pady=4)

        tk.Checkbutton(
            form,
            text='Open captures in a window',
            variable=windowed_value,
        ).grid(row=3, column=0, columnspan=2, sticky='w', pady=(8, 4))

        def save():
            try:
                delay = float(delay_value.get().strip() or '0')
            except ValueError:
                messagebox.showerror('Boomer Preferences', 'Delay must be a number.')
                return

            shortcut = shortcut_value.get().strip()
            if not shortcut:
                messagebox.showerror('Boomer Preferences', 'Shortcut cannot be empty.')
                return

            self.config = TrayConfig(
                shortcut=shortcut,
                windowed=windowed_value.get(),
                delay=max(0.0, delay),
                config_file=config_file_value.get().strip() or str(BOOMER_CONFIG_FILE),
            )
            self._save_config()
            self._restart_hotkey_listener()
            self._refresh_menu()
            root.destroy()

        buttons = tk.Frame(form)
        buttons.grid(row=4, column=0, columnspan=2, sticky='e', pady=(12, 0))
        tk.Button(buttons, text='Open Config File', command=self._open_config_file).grid(row=0, column=0, padx=(0, 6))
        tk.Button(buttons, text='Cancel', command=root.destroy).grid(row=0, column=1, padx=(0, 6))
        tk.Button(buttons, text='Save', command=save).grid(row=0, column=2)

        root.mainloop()

    def _open_config_file(self):
        self._ensure_config_files()
        opener = os.environ.get('EDITOR')
        if opener:
            subprocess.Popen([opener, str(TRAY_CONFIG_FILE)], start_new_session=True)
        else:
            subprocess.Popen(['xdg-open', str(TRAY_CONFIG_FILE)], start_new_session=True)

    def _start_hotkey_listener(self):
        try:
            from pynput import keyboard
            self._hotkey_listener = keyboard.GlobalHotKeys({
                self.config.shortcut: self.capture_for_hotkey,
            })
            self._hotkey_listener.start()
        except Exception as error:
            print(f'Could not register global shortcut {self.config.shortcut!r}: {error}', file=sys.stderr)
            self._hotkey_listener = None

    def _stop_hotkey_listener(self):
        if self._hotkey_listener is None:
            return
        self._hotkey_listener.stop()
        self._hotkey_listener = None

    def _restart_hotkey_listener(self):
        self._stop_hotkey_listener()
        self._start_hotkey_listener()

    def _load_config(self) -> TrayConfig:
        self._ensure_config_files()
        parser = configparser.ConfigParser()
        parser.read(TRAY_CONFIG_FILE)
        section = parser['tray'] if parser.has_section('tray') else {}
        return TrayConfig(
            shortcut=section.get('shortcut', TrayConfig.shortcut),
            windowed=section.get('windowed', str(TrayConfig.windowed)).lower() == 'true',
            delay=float(section.get('delay', str(TrayConfig.delay))),
            config_file=section.get('config_file', TrayConfig.config_file),
        )

    def _save_config(self):
        self._ensure_config_files()
        parser = configparser.ConfigParser()
        parser['tray'] = {
            'shortcut': self.config.shortcut,
            'windowed': str(self.config.windowed).lower(),
            'delay': str(self.config.delay),
            'config_file': self.config.config_file,
        }
        with open(TRAY_CONFIG_FILE, 'w') as config_file:
            parser.write(config_file)

    def _ensure_config_files(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not TRAY_CONFIG_FILE.exists():
            parser = configparser.ConfigParser()
            parser['tray'] = {
                'shortcut': TrayConfig.shortcut,
                'windowed': str(TrayConfig.windowed).lower(),
                'delay': str(TrayConfig.delay),
                'config_file': TrayConfig.config_file,
            }
            with open(TRAY_CONFIG_FILE, 'w') as config_file:
                parser.write(config_file)


def main():
    BoomerTray().run()


if __name__ == '__main__':
    main()