from dataclasses import dataclass, field
import math

VELOCITY_THRESHOLD = 15.0


@dataclass
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: 'Vec2') -> 'Vec2':
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: 'Vec2') -> 'Vec2':
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, s: float) -> 'Vec2':
        return Vec2(self.x * s, self.y * s)

    def __truediv__(self, s: float) -> 'Vec2':
        return Vec2(self.x / s, self.y / s)

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)


@dataclass
class Mouse:
    curr: Vec2 = field(default_factory=Vec2)
    prev: Vec2 = field(default_factory=Vec2)
    drag: bool = False


@dataclass
class Camera:
    position: Vec2 = field(default_factory=Vec2)
    velocity: Vec2 = field(default_factory=Vec2)
    scale: float = 1.0
    delta_scale: float = 0.0
    scale_pivot: Vec2 = field(default_factory=Vec2)


def update_camera(camera: Camera, config, dt: float, mouse: Mouse,
                  window_width: float, window_height: float):
    if abs(camera.delta_scale) > 0.5:
        half = Vec2(window_width * 0.5, window_height * 0.5)
        p0 = (camera.scale_pivot - half) / camera.scale
        camera.scale = max(camera.scale + camera.delta_scale * dt, config.min_scale)
        p1 = (camera.scale_pivot - half) / camera.scale
        camera.position = camera.position + (p0 - p1)
        camera.delta_scale -= camera.delta_scale * dt * config.scale_friction

    if not mouse.drag and camera.velocity.length() > VELOCITY_THRESHOLD:
        camera.position = camera.position + camera.velocity * dt
        camera.velocity = camera.velocity - camera.velocity * (dt * config.drag_friction)
