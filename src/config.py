from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    min_scale: float = 0.01
    scroll_speed: float = 1.5
    drag_friction: float = 6.0
    scale_friction: float = 4.0


DEFAULT_CONFIG = Config()


def load_config(file_path: str) -> Config:
    config = Config()
    with open(file_path) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            if key == 'min_scale':
                config.min_scale = float(value)
            elif key == 'scroll_speed':
                config.scroll_speed = float(value)
            elif key == 'drag_friction':
                config.drag_friction = float(value)
            elif key == 'scale_friction':
                config.scale_friction = float(value)
            else:
                raise ValueError(f"Unknown config key: {key!r}")
    return config


def generate_default_config(file_path: str):
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w') as f:
        f.write(f"min_scale = {DEFAULT_CONFIG.min_scale}\n")
        f.write(f"scroll_speed = {DEFAULT_CONFIG.scroll_speed}\n")
        f.write(f"drag_friction = {DEFAULT_CONFIG.drag_friction}\n")
        f.write(f"scale_friction = {DEFAULT_CONFIG.scale_friction}\n")
