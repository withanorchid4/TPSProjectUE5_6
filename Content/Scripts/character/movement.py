# -*- encoding: utf-8 -*-
"""角色移动组件"""

import ue


class MovementComponent:
    """处理角色的移动和跳跃逻辑"""
    
    DEFAULT_MOVE_SPEED = 1.0
    DEFAULT_JUMP_VELOCITY = 420.0
    
    def __init__(self, owner):
        """
        初始化移动组件
        
        Args:
            owner: 角色实例 (ue.Character)
        """
        self.owner = owner
        self.move_speed = self.DEFAULT_MOVE_SPEED
        self.jump_velocity = self.DEFAULT_JUMP_VELOCITY
    
    def move_forward(self, value: float):
        """
        前后移动
        
        Args:
            value: 移动值，正数为前，负数为后
        """
        if value != 0.0:
            forward = self.owner.GetActorForwardVector()
            self.owner.AddMovementInput(forward, value)
    
    def move_right(self, value: float):
        """
        左右移动
        
        Args:
            value: 移动值，正数为右，负数为左
        """
        if value != 0.0:
            right = self.owner.GetActorRightVector()
            self.owner.AddMovementInput(right, value)
    
    def jump(self):
        """执行跳跃"""
        if self.is_grounded():
            self.owner.Jump()
    
    def stop_jumping(self):
        """停止跳跃"""
        self.owner.StopJumping()
    
    def is_grounded(self) -> bool:
        """检测是否在地面"""
        movement_comp = self.owner.GetCharacterMovement()
        if movement_comp:
            return not movement_comp.IsFalling()
        return True
