# -*- encoding: utf-8 -*-
"""角色控制模块"""

from .base_character import BaseCharacter
from .movement import MovementComponent
from .camera import CameraComponent
from .shooting import ShootingComponent
from .input_handler import InputHandler
# from .bullet import Bullet          # 未使用，射击逻辑在 ShootingComponent 的 LineTrace 中
# from .hitscan_bullet import HitscanBullet  # 未使用，同上
from .magic_arrow import MagicArrow

__all__ = [
    'BaseCharacter',
    'MovementComponent',
    'CameraComponent',
    'ShootingComponent',
    'InputHandler',
    'MagicArrow',
]
