#!/usr/bin/env python3
import argparse
import ctypes
import os
import sys
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk

import OpenGL.GL as gl
import numpy as np

from config import Config, DEFAULT_CONFIG, generate_default_config, load_config
from navigation import Camera, Mouse, Vec2, update_camera
from screenshot import take_screenshot

SHADER_DIR = Path(__file__).parent

INITIAL_FL_DELTA_RADIUS = 250.0
FL_DELTA_RADIUS_DECELERATION = 10.0


class Flashlight:
    def __init__(self):
        self.is_enabled = False
        self.shadow = 0.0
        self.radius = 200.0
        self.delta_radius = 0.0

    def update(self, dt: float):
        if abs(self.delta_radius) > 1.0:
            self.radius = max(0.0, self.radius + self.delta_radius * dt)
            self.delta_radius -= self.delta_radius * FL_DELTA_RADIUS_DECELERATION * dt

        if self.is_enabled:
            self.shadow = min(self.shadow + 6.0 * dt, 0.8)
        else:
            self.shadow = max(self.shadow - 6.0 * dt, 0.0)


class BoomerWindow(Gtk.ApplicationWindow):
    def __init__(self, application, config: Config, config_file: str,
                 screenshot, windowed: bool):
        super().__init__(application=application)
        self.config = config
        self.config_file = config_file
        self.screenshot_img = screenshot
        self.windowed = windowed

        self.camera = Camera()
        self.mouse = Mouse()
        self.flashlight = Flashlight()
        self.mirror = False
        self._last_frame_time = None
        self._rate = 60.0
        self._gl_ready = False

        self.set_title('boomer')
        self.set_focusable(True)

        if not windowed:
            self.fullscreen()

        self.gl_area = Gtk.GLArea()
        self.gl_area.set_auto_render(True)
        self.gl_area.set_required_version(3, 3)
        self.gl_area.connect('realize', self._on_realize)
        self.gl_area.connect('unrealize', self._on_unrealize)
        self.gl_area.connect('render', self._on_render)
        self.set_child(self.gl_area)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect('key-pressed', self._on_key_pressed)
        self.add_controller(key_ctrl)

        motion_ctrl = Gtk.EventControllerMotion()
        motion_ctrl.connect('motion', self._on_motion)
        self.gl_area.add_controller(motion_ctrl)

        click_ctrl = Gtk.GestureClick()
        click_ctrl.set_button(1)
        click_ctrl.connect('pressed', self._on_button_pressed)
        click_ctrl.connect('released', self._on_button_released)
        self.gl_area.add_controller(click_ctrl)

        scroll_ctrl = Gtk.EventControllerScroll()
        scroll_ctrl.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_ctrl.connect('scroll', self._on_scroll)
        self.gl_area.add_controller(scroll_ctrl)

        self.gl_area.add_tick_callback(self._on_tick)
        self._detect_refresh_rate()

    def _detect_refresh_rate(self):
        display = self.get_display()
        if not display:
            return
        monitors = display.get_monitors()
        if monitors.get_n_items() > 0:
            monitor = monitors.get_item(0)
            rate_mhz = monitor.get_refresh_rate()
            if rate_mhz > 0:
                self._rate = rate_mhz / 1000.0

    # --- OpenGL lifecycle ---

    def _on_realize(self, area):
        area.make_current()
        if area.get_error():
            print(f"GLArea error: {area.get_error()}", file=sys.stderr)
            return
        self._setup_gl()

    def _on_unrealize(self, area):
        area.make_current()
        self._cleanup_gl()

    def _setup_gl(self):
        vert_src = (SHADER_DIR / 'vert.glsl').read_text()
        frag_src = (SHADER_DIR / 'frag.glsl').read_text()
        self.shader_program = self._compile_program(vert_src, frag_src)

        img = self.screenshot_img.convert('RGBA')
        self.img_width, self.img_height = img.size
        img_data = np.frombuffer(img.tobytes(), dtype=np.uint8)

        w, h = float(self.img_width), float(self.img_height)
        vertices = np.array([
            w,   0.0, 1.0, 1.0,   # top right
            w,   h,   1.0, 0.0,   # bottom right
            0.0, h,   0.0, 0.0,   # bottom left
            0.0, 0.0, 0.0, 1.0,   # top left
        ], dtype=np.float32)
        indices = np.array([0, 1, 3, 1, 2, 3], dtype=np.uint32)

        self.vao = gl.glGenVertexArrays(1)
        self.vbo, self.ebo = gl.glGenBuffers(2)

        gl.glBindVertexArray(self.vao)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)

        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, gl.GL_STATIC_DRAW)

        stride = 4 * ctypes.sizeof(ctypes.c_float)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride,
                                 ctypes.c_void_p(2 * ctypes.sizeof(ctypes.c_float)))
        gl.glEnableVertexAttribArray(1)

        self.texture = gl.glGenTextures(1)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                        self.img_width, self.img_height,
                        0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data)
        gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER)

        gl.glUseProgram(self.shader_program)
        gl.glUniform1i(gl.glGetUniformLocation(self.shader_program, 'tex'), 0)

        self._gl_ready = True

    def _cleanup_gl(self):
        if self._gl_ready:
            gl.glDeleteVertexArrays(1, [self.vao])
            gl.glDeleteBuffers(1, [self.vbo])
            gl.glDeleteBuffers(1, [self.ebo])
            gl.glDeleteTextures(1, [self.texture])
            gl.glDeleteProgram(self.shader_program)
            self._gl_ready = False

    def _compile_shader(self, source: str, kind: int) -> int:
        shader = gl.glCreateShader(kind)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
            log = gl.glGetShaderInfoLog(shader)
            raise RuntimeError(f"Shader compile error:\n{log.decode()}")
        return shader

    def _compile_program(self, vert_src: str, frag_src: str) -> int:
        vert = self._compile_shader(vert_src, gl.GL_VERTEX_SHADER)
        frag = self._compile_shader(frag_src, gl.GL_FRAGMENT_SHADER)
        program = gl.glCreateProgram()
        gl.glAttachShader(program, vert)
        gl.glAttachShader(program, frag)
        gl.glLinkProgram(program)
        gl.glDeleteShader(vert)
        gl.glDeleteShader(frag)
        if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
            log = gl.glGetProgramInfoLog(program)
            raise RuntimeError(f"Shader link error:\n{log.decode()}")
        return program

    # --- Render ---

    def _on_render(self, area, context):
        if not self._gl_ready:
            return False

        scale = area.get_scale_factor()
        width = area.get_width() * scale
        height = area.get_height() * scale

        gl.glViewport(0, 0, width, height)
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        p = self.shader_program
        loc = gl.glGetUniformLocation
        cam = self.camera
        fl = self.flashlight

        gl.glUseProgram(p)
        gl.glUniform2f(loc(p, 'cameraPos'), cam.position.x, cam.position.y)
        gl.glUniform1f(loc(p, 'cameraScale'), cam.scale)
        gl.glUniform2f(loc(p, 'screenshotSize'), float(self.img_width), float(self.img_height))
        gl.glUniform2f(loc(p, 'windowSize'), float(width), float(height))
        gl.glUniform2f(loc(p, 'cursorPos'), self.mouse.curr.x * scale, self.mouse.curr.y * scale)
        gl.glUniform1f(loc(p, 'flShadow'), fl.shadow)
        gl.glUniform1f(loc(p, 'flRadius'), fl.radius)
        gl.glUniform1f(loc(p, 'cameraScale'), cam.scale)
        gl.glUniform1i(loc(p, 'mirror'), 1 if self.mirror else 0)

        gl.glBindVertexArray(self.vao)
        gl.glDrawElements(gl.GL_TRIANGLES, 6, gl.GL_UNSIGNED_INT, None)

        return True

    # --- Tick (physics update) ---

    def _on_tick(self, widget, frame_clock):
        now = frame_clock.get_frame_time() / 1_000_000.0
        if self._last_frame_time is None:
            self._last_frame_time = now
            return GLib.SOURCE_CONTINUE

        dt = now - self._last_frame_time
        self._last_frame_time = now

        if dt <= 0.0 or dt > 0.1:
            dt = 1.0 / self._rate

        if self._gl_ready:
            scale = widget.get_scale_factor()
            w = float(widget.get_width() * scale)
            h = float(widget.get_height() * scale)
            update_camera(self.camera, self.config, dt, self.mouse, w, h)
            self.flashlight.update(dt)

        return GLib.SOURCE_CONTINUE

    # --- Input ---

    def _scroll_up(self, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and self.flashlight.is_enabled:
            self.flashlight.delta_radius += INITIAL_FL_DELTA_RADIUS
        else:
            self.camera.delta_scale += self.config.scroll_speed
            self.camera.scale_pivot = Vec2(self.mouse.curr.x, self.mouse.curr.y)

    def _scroll_down(self, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and self.flashlight.is_enabled:
            self.flashlight.delta_radius -= INITIAL_FL_DELTA_RADIUS
        else:
            self.camera.delta_scale -= self.config.scroll_speed
            self.camera.scale_pivot = Vec2(self.mouse.curr.x, self.mouse.curr.y)

    def _on_key_pressed(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_equal:
            self._scroll_up(state)
        elif keyval == Gdk.KEY_minus:
            self._scroll_down(state)
        elif keyval == Gdk.KEY_0:
            self.camera.scale = 1.0
            self.camera.delta_scale = 0.0
            self.camera.position = Vec2()
            self.camera.velocity = Vec2()
            self.mirror = False
        elif keyval in (Gdk.KEY_q, Gdk.KEY_Escape):
            self.close()
        elif keyval == Gdk.KEY_r:
            if os.path.exists(self.config_file):
                self.config = load_config(self.config_file)
        elif keyval == Gdk.KEY_m:
            self.camera.position.x += (
                self.img_width / self.camera.scale
                - 2.0 * (self.mouse.curr.x / self.camera.scale + self.camera.position.x)
            )
            self.mirror = not self.mirror
        elif keyval == Gdk.KEY_f:
            self.flashlight.is_enabled = not self.flashlight.is_enabled
        return True

    def _on_motion(self, ctrl, x, y):
        self.mouse.curr = Vec2(x, y)
        if self.mouse.drag:
            delta = self.mouse.prev / self.camera.scale - self.mouse.curr / self.camera.scale
            self.camera.position = self.camera.position + delta
            self.camera.velocity = delta * self._rate
        self.mouse.prev = Vec2(x, y)

    def _on_button_pressed(self, gesture, n_press, x, y):
        self.mouse.prev = Vec2(x, y)
        self.mouse.drag = True
        self.camera.velocity = Vec2()

    def _on_button_released(self, gesture, n_press, x, y):
        self.mouse.drag = False

    def _on_scroll(self, ctrl, dx, dy):
        state = ctrl.get_current_event_state()
        if dy < 0:
            self._scroll_up(state)
        elif dy > 0:
            self._scroll_down(state)
        return True


class BoomerApp(Gtk.Application):
    def __init__(self, config_file: str, delay_sec: float, windowed: bool):
        super().__init__(application_id='io.github.tsoding.boomer-port')
        self.config_file = config_file
        self.delay_sec = delay_sec
        self.windowed = windowed
        self.connect('activate', self._on_activate)

    def _on_activate(self, app):
        if self.delay_sec > 0:
            time.sleep(self.delay_sec)

        config = DEFAULT_CONFIG
        if os.path.exists(self.config_file):
            config = load_config(self.config_file)
        else:
            print(f"{self.config_file} doesn't exist. Using default values.", file=sys.stderr)

        print(f"Using config: {config}")

        try:
            screenshot = take_screenshot()
        except RuntimeError as e:
            sys.exit(str(e))

        window = BoomerWindow(
            application=app,
            config=config,
            config_file=self.config_file,
            screenshot=screenshot,
            windowed=self.windowed,
        )
        window.present()


def main():
    boomer_dir = Path.home() / '.config' / 'boomer'
    default_config = str(boomer_dir / 'config')

    parser = argparse.ArgumentParser(
        prog='boomer',
        description='Boomer — screen zoomer for GNOME 46',
    )
    parser.add_argument('-d', '--delay', type=float, default=0.0, metavar='seconds',
                        help='delay start by N seconds')
    parser.add_argument('-w', '--windowed', action='store_true',
                        help='windowed mode instead of fullscreen')
    parser.add_argument('-c', '--config', default=default_config, metavar='filepath',
                        help='path to config file')
    parser.add_argument('--new-config', nargs='?', const=default_config, metavar='filepath',
                        help='generate default config (at filepath or default location)')

    args = parser.parse_args()

    if args.new_config is not None:
        target = args.new_config
        if os.path.exists(target):
            answer = input(f"File {target} already exists. Replace it? [yn] ")
            if answer.strip() != 'y':
                sys.exit("Disaster prevented")
        generate_default_config(target)
        sys.exit(f"Generated config at {target}")

    app = BoomerApp(
        config_file=args.config,
        delay_sec=args.delay,
        windowed=args.windowed,
    )
    sys.exit(app.run(None))


if __name__ == '__main__':
    main()
