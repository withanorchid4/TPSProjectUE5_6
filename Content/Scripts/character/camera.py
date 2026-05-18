# -*- encoding: utf-8 -*-
"""TPS 摄像机组件"""

import ue


class CameraComponent:
    """TPS 越肩摄像机控制"""
    
    # 默认摄像机参数
    DEFAULT_ARM_LENGTH = 300.0
    DEFAULT_SOCKET_OFFSET = (50.0, 100.0)  # Y, Z 偏移（越肩效果）
    DEFAULT_ROTATION_SPEED = 2.0
    
    # 瞄准模式参数
    AIM_ARM_LENGTH = 50.0
    AIM_SOCKET_OFFSET = (30.0, 80.0)  # Y, Z 偏移（瞄准时更靠近角色）
    
    def __init__(self, owner):
        """
        初始化摄像机组件
        
        Args:
            owner: 角色实例 (ue.Character)
        """
        self.owner = owner
        self.spring_arm = None
        self.camera = None
        
        # 摄像机参数
        self.arm_length = self.DEFAULT_ARM_LENGTH
        self.socket_offset = self.DEFAULT_SOCKET_OFFSET
        self.rotation_speed = self.DEFAULT_ROTATION_SPEED
        
        # 瞄准状态
        self._is_aiming = False
    
    def setup(self):
        """设置摄像机组件"""
        # 查找现有的 SpringArm 组件
        self.spring_arm = self.owner.GetComponentByClass(ue.SpringArmComponent)
        
        if not self.spring_arm:
            # 创建新的 SpringArm
            self.spring_arm = ue.NewObject(ue.SpringArmComponent, self.owner, "CameraSpringArm")
            self.spring_arm.SetupAttachment(self.owner.GetCapsuleComponent())
            self.spring_arm.RegisterComponent()
        
        # 配置 SpringArm
        self.spring_arm.TargetArmLength = self.arm_length
        self.spring_arm.SocketOffset = ue.Vector(
            0.0,
            self.socket_offset[0],  # Y
            self.socket_offset[1]   # Z
        )
        self.spring_arm.bUsePawnControlRotation = True
        self.spring_arm.bEnableCameraLag = True
        self.spring_arm.CameraLagSpeed = 6.0
        self.spring_arm.bDoCollisionTest = True
        self.spring_arm.ProbeSize = 12.0
        
        # 查找现有的 Camera 组件
        self.camera = self.owner.GetComponentByClass(ue.CameraComponent)
        
        if not self.camera:
            # 创建新的 Camera
            self.camera = ue.NewObject(ue.CameraComponent, self.spring_arm, "TPSCamera")
            self.camera.RegisterComponent()
        
        ue.Log(f"CameraComponent: Setup complete, arm_length={self.arm_length}")
    
    def tick(self, delta_time: float):
        """
        每帧更新摄像机参数
        
        Args:
            delta_time: 帧间隔时间
        """
        # SpringArm 的 CameraLag 会自动处理平滑过渡
        pass
    
    def update_rotation(self, yaw_delta: float, pitch_delta: float):
        """
        更新摄像机旋转
        
        Args:
            yaw_delta: Yaw 旋转增量
            pitch_delta: Pitch 旋转增量
        """
        self.owner.AddControllerYawInput(yaw_delta)
        self.owner.AddControllerPitchInput(pitch_delta)
    
    def set_aiming(self, is_aiming: bool):
        """
        设置瞄准状态
        
        Args:
            is_aiming: 是否瞄准
        """
        # 收枪时不能开镜
        if is_aiming and not getattr(self.owner, '_is_weapon_drawn', False):
            return
        
        self._is_aiming = is_aiming
        
        if not self.spring_arm:
            return
        
        if is_aiming:
            # 开镜：拉近摄像机
            self.spring_arm.TargetArmLength = self.AIM_ARM_LENGTH
            self.spring_arm.SocketOffset = ue.Vector(
                0.0,
                self.AIM_SOCKET_OFFSET[0],
                self.AIM_SOCKET_OFFSET[1]
            )
            
            # 开镜时：角色转向摄像机方向
            self._rotate_character_to_camera()
            
            # 开镜时限制移动速度
            movement = self.owner.CharacterMovement
            if movement:
                movement.MaxWalkSpeed = 300.0
            
            # 更新动画蓝图的瞄准变量
            self._set_anim_aiming(True)
            
            ue.Log("CameraComponent: Aiming mode ON")
        else:
            # 关闭瞄准：恢复默认摄像机距离
            self.spring_arm.TargetArmLength = self.DEFAULT_ARM_LENGTH
            self.spring_arm.SocketOffset = ue.Vector(
                0.0,
                self.DEFAULT_SOCKET_OFFSET[0],
                self.DEFAULT_SOCKET_OFFSET[1]
            )
            
            # 恢复移动速度
            movement = self.owner.CharacterMovement
            if movement:
                walk_speed = self.owner.movement.WALK_SPEED if self.owner.movement else 300.0
                movement.MaxWalkSpeed = walk_speed
            
            # 更新动画蓝图的瞄准变量
            self._set_anim_aiming(False)
            
            ue.Log("CameraComponent: Aiming mode OFF")
    
    def _rotate_character_to_camera(self):
        """开镜时让角色转向摄像机方向"""
        controller = self.owner.GetController()
        if not controller:
            return
        
        # 获取摄像机的 Yaw（只转水平方向）
        control_rotation = controller.GetControlRotation()
        target_yaw = control_rotation.Yaw
        
        # 设置角色旋转（只改 Yaw，保持 Pitch 和 Roll）
        current_rotation = self.owner.GetActorRotation()
        new_rotation = ue.Rotator(current_rotation.Pitch, target_yaw, current_rotation.Roll)
        # SetActorRotation(Rotator, bTeleportPhysics)
        self.owner.SetActorRotation(new_rotation, False)
    
    def _set_anim_aiming(self, is_aiming: bool):
        """
        更新动画蓝图的瞄准变量
        
        Args:
            is_aiming: 是否瞄准
        """
        mesh = self.owner.Mesh
        if not mesh:
            return
        
        anim_instance = mesh.GetAnimInstance()
        if not anim_instance:
            return
        
        # 设置动画蓝图中的 bIsAiming 变量
        # 变量名需要和动画蓝图中的变量名一致
        anim_instance.bIsAiming = is_aiming
    
    def is_aiming(self) -> bool:
        """检查是否正在瞄准"""
        return self._is_aiming
    
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
