# -*- encoding: utf-8 -*-
"""TPS 摄像机组件"""

import ue


class CameraComponent:
    """TPS 越肩摄像机控制"""
    
    # 默认摄像机参数
    DEFAULT_ARM_LENGTH = 300.0
    DEFAULT_SOCKET_OFFSET = (0.0, 50.0, 100.0)  # Y, Z 偏移（越肩效果）
    DEFAULT_ROTATION_SPEED = 2.0
    
    def __init__(self, owner):
        """
        初始化摄像机组件
        
        Args:
            owner: 角色实例 (ue.Character)
        """
        self.owner = owner
        self.spring_arm = None
        self.camera = None
        self.arm_length = self.DEFAULT_ARM_LENGTH
        self.socket_offset = self.DEFAULT_SOCKET_OFFSET
        self.rotation_speed = self.DEFAULT_ROTATION_SPEED
    
    def setup(self):
        """设置摄像机组件"""
        # 查找现有的 SpringArm 组件
        self.spring_arm = self.owner.FindComponentByClass(ue.SpringArmComponent)
        
        if not self.spring_arm:
            # 创建新的 SpringArm
            self.spring_arm = ue.NewObject(ue.SpringArmComponent, self.owner, "CameraSpringArm")
            self.spring_arm.SetupAttachment(self.owner.GetCapsuleComponent())
        
        # 配置 SpringArm
        self.spring_arm.TargetArmLength = self.arm_length
        self.spring_arm.SocketOffset = ue.Vector(
            0.0,
            self.socket_offset[0],  # Y
            self.socket_offset[1]   # Z
        )
        self.spring_arm.bUsePawnControlRotation = True
        self.spring_arm.bEnableCameraLag = True
        self.spring_arm.CameraLagSpeed = 3.0
        
        # 查找现有的 Camera 组件
        self.camera = self.owner.FindComponentByClass(ue.CameraComponent)
        
        if not self.camera:
            # 创建新的 Camera
            self.camera = ue.NewObject(ue.CameraComponent, self.spring_arm, "TPSCamera")
        
        ue.Log(f"CameraComponent setup complete, arm_length={self.arm_length}")
    
    def update_rotation(self, yaw_delta: float, pitch_delta: float):
        """
        更新摄像机旋转
        
        Args:
            yaw_delta: Yaw 旋转增量
            pitch_delta: Pitch 旋转增量
        """
        self.owner.AddControllerYawInput(yaw_delta * self.rotation_speed)
        self.owner.AddControllerPitchInput(pitch_delta * self.rotation_speed)
    
    def set_arm_length(self, length: float):
        """设置摄像机距离"""
        self.arm_length = length
        if self.spring_arm:
            self.spring_arm.TargetArmLength = length
    
    def set_socket_offset(self, y: float, z: float):
        """设置摄像机偏移"""
        self.socket_offset = (y, z)
        if self.spring_arm:
            self.spring_arm.SocketOffset = ue.Vector(0.0, y, z)
