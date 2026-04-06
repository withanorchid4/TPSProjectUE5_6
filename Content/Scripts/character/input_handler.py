# -*- encoding: utf-8 -*-
"""输入处理器抽象基类"""

from abc import ABC, abstractmethod
import ue


class InputHandler(ABC):
    """输入处理器抽象基类，定义输入处理的接口"""
    
    def __init__(self, owner):
        """
        初始化输入处理器
        
        Args:
            owner: 角色实例 (ue.Character)
        """
        self.owner = owner
        self.movement = None
        self.camera = None
        self.shooting = None
    
    def set_components(self, movement, camera, shooting):
        """
        设置组件引用
        
        Args:
            movement: MovementComponent 实例
            camera: CameraComponent 实例
            shooting: ShootingComponent 实例
        """
        self.movement = movement
        self.camera = camera
        self.shooting = shooting
        ue.Log("InputHandler: components set")
    
    @abstractmethod
    def bind(self):
        """绑定输入事件"""
        pass
    
    @abstractmethod
    def unbind(self):
        """解绑输入事件"""
        pass
    
    @abstractmethod
    def tick(self, delta_time: float):
        """
        每帧更新
        
        Args:
            delta_time: 帧间隔时间
        """
        pass
