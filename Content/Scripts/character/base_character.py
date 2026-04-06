# -*- encoding: utf-8 -*-
"""角色基类"""

import ue
from .movement import MovementComponent
from .camera import CameraComponent
from .shooting import ShootingComponent


@ue.uclass()
class BaseCharacter(ue.Character):
    """
    角色基类，使用组件组合模式
    
    子类可以继承并重写各方法来自定义行为
    """
    
    def __init_pyobj__(self):
        """初始化 Python 变量（NePy 要求用 __init_pyobj__ 代替 __init__）"""
        # 组件实例
        self.movement = None
        self.camera = None
        self.shooting = None
        self.input_handler = None
    
    def ReceiveBeginPlay(self):
        """角色开始播放时调用"""
        ue.Log(f"{self} ReceiveBeginPlay")
        
        # 初始化组件
        self._init_components()
    
    def _init_components(self):
        """初始化所有组件"""
        # 创建移动组件
        self.movement = MovementComponent(self)
        
        # 创建摄像机组件
        self.camera = CameraComponent(self)
        self.camera.setup()
        
        # 创建射击组件
        self.shooting = ShootingComponent(self)
        
        ue.Log(f"BaseCharacter: Components initialized for {self}")
    
    def set_input_handler(self, handler):
        """
        设置输入处理器
        
        Args:
            handler: InputHandler 实例
        """
        self.input_handler = handler
        handler.set_components(self.movement, self.camera, self.shooting)
        handler.bind()
        ue.Log(f"BaseCharacter: Input handler set to {handler.__class__.__name__}")
    
    def set_bullet_class(self, bullet_class):
        """
        设置子弹类
        
        Args:
            bullet_class: 子弹 Actor 类
        """
        if self.shooting:
            self.shooting.set_bullet_class(bullet_class)
    
    def ReceiveEndPlay(self, end_play_reason):
        """角色结束播放时调用"""
        if self.input_handler:
            self.input_handler.unbind()
        ue.Log(f"{self} ReceiveEndPlay")
