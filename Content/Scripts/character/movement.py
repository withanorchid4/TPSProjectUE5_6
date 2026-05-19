# -*- encoding: utf-8 -*-
"""角色移动组件"""

import ue


class MovementComponent:
    """处理角色的移动和跳跃逻辑"""
    
    WALK_SPEED = 300.0
    JOG_SPEED = 600.0
    DEFAULT_JUMP_VELOCITY = 420.0
    
    def __init__(self, owner):
        """
        初始化移动组件
        
        Args:
            owner: 角色实例 (ue.Character)
        """
        self.owner = owner
        self.jump_velocity = self.DEFAULT_JUMP_VELOCITY
        self._is_sprinting = False
        
        # 设置默认行走速度
        self._set_max_walk_speed(self.WALK_SPEED)
    
    def move_forward(self, value: float):
        """
        前后移动（基于摄像机方向）
        
        Args:
            value: 移动值，正数为前，负数为后
        """
        if value != 0.0 and self.owner.Controller:
            # 获取 Controller 的 Yaw 旋转
            rotation = self.owner.Controller.GetControlRotation()
            # 使用 Yaw 获取前向向量（忽略 Pitch 和 Roll）
            direction = ue.KismetMathLibrary.GetForwardVector(ue.Rotator(0, rotation.Yaw, 0))
            self.owner.AddMovementInput(direction, value)
    
    def move_right(self, value: float):
        """
        左右移动（基于摄像机方向）
        
        Args:
            value: 移动值，正数为右，负数为左
        """
        if value != 0.0 and self.owner.Controller:
            rotation = self.owner.Controller.GetControlRotation()
            direction = ue.KismetMathLibrary.GetRightVector(ue.Rotator(0, rotation.Yaw, 0))
            self.owner.AddMovementInput(direction, value)
    
    def jump(self):
        """执行跳跃"""
        if self.is_grounded():
            self.owner.Jump()
    
    def stop_jumping(self):
        """停止跳跃"""
        self.owner.StopJumping()
    
    def is_grounded(self) -> bool:
        """检测是否在地面"""
        # NePy: 使用属性 CharacterMovement，而非方法 GetCharacterMovement()
        movement_comp = self.owner.CharacterMovement
        if movement_comp:
            return not movement_comp.IsFalling()
        return True
    
    def start_sprint(self):
        """开始冲刺（按住 Shift）"""
        # 瞄准或射击时禁止冲刺
        camera = getattr(self.owner, 'camera', None)
        if camera and camera.is_aiming():
            return
        shooting = getattr(self.owner, 'shooting', None)
        if shooting and shooting.is_firing():
            return
        
        self._is_sprinting = True
        self._set_max_walk_speed(self.JOG_SPEED)
        ue.Log(f"MovementComponent: Sprint ON (speed={self.JOG_SPEED})")
    
    def stop_sprint(self):
        """停止冲刺（松开 Shift）"""
        self._is_sprinting = False
        self._set_max_walk_speed(self.WALK_SPEED)
    
    def is_sprinting(self) -> bool:
        """是否正在冲刺"""
        return self._is_sprinting
    
    def _set_max_walk_speed(self, speed: float):
        """设置角色最大行走速度"""
        movement_comp = self.owner.CharacterMovement
        if movement_comp:
            movement_comp.MaxWalkSpeed = speed