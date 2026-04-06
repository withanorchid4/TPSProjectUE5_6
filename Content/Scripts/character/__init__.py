# -*- encoding: utf-8 -*-
"""角色控制模块"""

from .base_character import BaseCharacter
from .movement import MovementComponent
from .camera import CameraComponent
from .shooting import ShootingComponent
from .input_handler import InputHandler

__all__ = [
    'BaseCharacter',
    'MovementComponent',
    'CameraComponent',
    'ShootingComponent',
    'InputHandler',
]
