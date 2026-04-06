# -*- encoding: utf-8 -*-
"""TPS 第三人称射击游戏角色"""

import ue


@ue.uclass()
class TPSCharacter(ue.Character):
    """
    TPS 第三人称射击游戏角色
    
    功能:
    - WASD 移动
    - 空格跳跃
    - 鼠标控制视角
    """
    
    def __init_pyobj__(self):
        """初始化 Python 变量"""
        pass
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        """角色开始播放时调用"""
        ue.LogWarning(f"TPSCharacter '{self}' ReceiveBeginPlay!")
        
        # TPS 角色配置：角色不跟随 Controller 旋转
        self.bUseControllerRotationYaw = False
        self.bUseControllerRotationPitch = False
        self.bUseControllerRotationRoll = False
        
        # 注意：bOrientRotationToMovement 需要在蓝图的 CharacterMovementComponent 中勾选
        
        # 绑定输入
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
        self.EnableInput(pc)
        
        input_comp = self.InputComponent
        if not input_comp:
            ue.LogError("TPSCharacter: No InputComponent!")
            return
        
        ue.Log("TPSCharacter: Binding inputs...")
        
        # 绑定移动轴
        input_comp.BindAxis("MoveForward", self._move_forward)
        input_comp.BindAxis("MoveRight", self._move_right)
        input_comp.BindAxis("Turn", self._turn)
        input_comp.BindAxis("LookUp", self._look_up)
        
        # 绑定跳跃
        input_comp.BindAction("Jump", ue.EInputEvent.IE_Pressed, self._jump)
        
        ue.LogWarning("TPSCharacter: Input bindings complete!")
    
    def _move_forward(self, value: float):
        """前后移动（基于摄像机方向）"""
        if value != 0.0 and self.Controller:
            # 获取 Controller 的 Yaw 旋转
            rotation = self.Controller.GetControlRotation()
            # 使用 KismetMathLibrary 获取前向向量
            direction = ue.KismetMathLibrary.GetForwardVector(ue.Rotator(0, rotation.Yaw, 0))
            self.AddMovementInput(direction, value)
    
    def _move_right(self, value: float):
        """左右移动（基于摄像机方向）"""
        if value != 0.0 and self.Controller:
            rotation = self.Controller.GetControlRotation()
            direction = ue.KismetMathLibrary.GetRightVector(ue.Rotator(0, rotation.Yaw, 0))
            self.AddMovementInput(direction, value)
    
    def _turn(self, value: float):
        """水平旋转视角"""
        if value != 0.0:
            ue.Log(f"_turn value: {value}")
            self.AddControllerYawInput(value)
    
    def _look_up(self, value: float):
        """垂直旋转视角"""
        if value != 0.0:
            ue.Log(f"_look_up value: {value}")
            # TPS 标准：鼠标向下看 = 相机向下，鼠标向上看 = 相机向上
            self.AddControllerPitchInput(value)
    
    def _jump(self):
        """跳跃"""
        self.Jump()
        ue.Log("TPSCharacter: Jump!")
    
    @ue.ufunction(override=True)
    def ReceiveEndPlay(self, end_play_reason):
        """角色结束播放时调用"""
        ue.Log(f"TPSCharacter '{self}' ReceiveEndPlay")