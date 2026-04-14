# -*- encoding: utf-8 -*-
"""
TPS 第三人称射击游戏角色

功能:
- WASD 移动
- 空格跳跃
- 鼠标控制视角
- 鼠标左键射击
- 鼠标右键瞄准
"""

import ue
from character.base_character import BaseCharacter
from character import Bullet
from input_handlers.keyboard_handler import KeyboardInputHandler


@ue.uclass()
class TPSCharacter(BaseCharacter):
    """
    TPS 第三人称射击游戏角色
    
    继承自 BaseCharacter，使用组件组合模式
    """
    
    def __init_pyobj__(self):
        """初始化 Python 变量"""
        BaseCharacter.__init_pyobj__(self)
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        """角色开始播放时调用"""
        ue.LogWarning(f"TPSCharacter '{self}' ReceiveBeginPlay!")
        
        # 调用父类初始化组件
        BaseCharacter.ReceiveBeginPlay(self)
        
        # TPS 角色配置：角色不跟随 Controller 旋转
        self.bUseControllerRotationYaw = False
        self.bUseControllerRotationPitch = False
        self.bUseControllerRotationRoll = False
        
        # 注意：bOrientRotationToMovement 需要在蓝图的 CharacterMovementComponent 中勾选
        
        # 设置子弹类（纯 Python 实现）
        self.set_bullet_class(Bullet)
        ue.Log("TPSCharacter: Bullet class set")
        
        # 设置输入处理器
        self._setup_input()
    
    def _setup_input(self):
        """设置输入绑定"""
        # 确保 InputConfig 已初始化（动态添加输入映射）
        try:
            import input_config
            input_config.InputConfig.setup()
        except Exception as e:
            ue.LogWarning(f"TPSCharacter: InputConfig setup failed: {e}")
        
        # 关键：需要手动获取 PlayerController 并 Possess
        pc = self.GetWorld().GetPlayerController()
        if not pc:
            ue.LogWarning("TPSCharacter: No PlayerController found!")
            return
        
        # 手动 Possess（这是 NePy 角色控制的必要步骤）
        pc.UnPossess()
        pc.Possess(self)
        
        # 设置输入处理器
        input_handler = KeyboardInputHandler(self)
        self.set_input_handler(input_handler)
        
        ue.LogWarning("TPSCharacter: Setup complete!")