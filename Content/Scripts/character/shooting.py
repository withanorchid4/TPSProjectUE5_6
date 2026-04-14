# -*- encoding: utf-8 -*-
"""射击组件"""

import ue


class ShootingComponent:
    """处理射击逻辑"""
    
    FIRE_MODE_SINGLE = "single"  # 点射
    FIRE_MODE_AUTO = "auto"      # 连射
    
    SINGLE_FIRE_RATE = 0.15      # 点射间隔（秒）
    AUTO_FIRE_RATE = 0.1         # 连射间隔（秒）
    MUZZLE_OFFSET_FORWARD = 100.0   # 枪口前方偏移
    MUZZLE_OFFSET_UP = 50.0         # 枪口高度偏移
    MUZZLE_OFFSET_RIGHT = 30.0      # 枪口右侧偏移（越肩）
    
    def __init__(self, owner):
        """
        初始化射击组件
        
        Args:
            owner: 角色实例 (ue.Character)
        """
        self.owner = owner
        self.bullet_class = None
        self.fire_rate = self.SINGLE_FIRE_RATE
        self.last_fire_time = -999.0
        
        # 射击模式
        self._fire_mode = self.FIRE_MODE_SINGLE
        self._is_firing = False
    
    def set_bullet_class(self, bullet_class):
        """
        设置子弹类
        
        Args:
            bullet_class: 子弹 Actor 类
        """
        self.bullet_class = bullet_class
        ue.Log(f"ShootingComponent: Bullet class set to: {bullet_class}")
    
    def _get_current_time(self) -> float:
        """获取当前游戏时间"""
        return self.owner.GetGameTimeSinceCreation()
    
    def can_shoot(self) -> bool:
        """检查是否可以射击"""
        if not self.bullet_class:
            ue.LogWarning("ShootingComponent: No bullet class set!")
            return False
        
        current_time = self._get_current_time()
        return (current_time - self.last_fire_time) >= self.fire_rate
    
    def start_firing(self):
        """开始射击（按住鼠标左键）"""
        self._is_firing = True
        
        # 立即发射第一颗子弹
        self.shoot()
    
    def stop_firing(self):
        """停止射击（松开鼠标左键）"""
        self._is_firing = False
    
    def toggle_fire_mode(self):
        """切换射击模式（点射/连射）"""
        if self._fire_mode == self.FIRE_MODE_SINGLE:
            self._fire_mode = self.FIRE_MODE_AUTO
            self.fire_rate = self.AUTO_FIRE_RATE
        else:
            self._fire_mode = self.FIRE_MODE_SINGLE
            self.fire_rate = self.SINGLE_FIRE_RATE
        
        mode_name = "连射" if self._fire_mode == self.FIRE_MODE_AUTO else "点射"
        ue.LogWarning(f"ShootingComponent: 切换为{mode_name}模式")
    
    def get_fire_mode(self) -> str:
        """获取当前射击模式"""
        return self._fire_mode
    
    def is_auto_mode(self) -> bool:
        """是否为连射模式"""
        return self._fire_mode == self.FIRE_MODE_AUTO
    
    def tick(self, delta_time: float):
        """
        每帧更新（用于连发射击）
        
        Args:
            delta_time: 帧间隔时间
        """
        if self._is_firing:
            self.shoot()
    
    def shoot(self):
        """执行射击"""
        if not self.can_shoot():
            return False
        
        controller = self.owner.GetController()
        if not controller:
            ue.LogWarning("ShootingComponent: No controller!")
            return False
        
        # 根据瞄准状态选择射击方向（混合模式）
        # - 腰射：用角色朝向
        # - 开镜：用摄像机方向（精确瞄准）
        is_aiming = False
        if hasattr(self.owner, 'camera') and self.owner.camera:
            is_aiming = self.owner.camera.is_aiming()
        
        if is_aiming:
            # 开镜：使用摄像机方向
            fire_rotation = controller.GetControlRotation()
        else:
            # 腰射：使用角色朝向
            fire_rotation = self.owner.GetActorRotation()
        
        # 获取角色位置
        actor_location = self.owner.GetActorLocation()
        
        # 计算枪口位置
        forward = ue.KismetMathLibrary.GetForwardVector(fire_rotation)
        right = ue.KismetMathLibrary.GetRightVector(fire_rotation)
        up = ue.KismetMathLibrary.GetUpVector(fire_rotation)
        
        spawn_location = (
            actor_location 
            + forward * self.MUZZLE_OFFSET_FORWARD
            + right * self.MUZZLE_OFFSET_RIGHT
            + up * self.MUZZLE_OFFSET_UP
        )
        
        # 生成子弹
        world = self.owner.GetWorld()
        bullet = world.SpawnActor(
            self.bullet_class,
            spawn_location,
            fire_rotation
        )
        
        if bullet:
            self.last_fire_time = self._get_current_time()
            ue.Log(f"ShootingComponent: Shot fired (aiming={is_aiming})")
            return True
        else:
            ue.LogWarning("ShootingComponent: Failed to spawn bullet!")
            return False
    
    def is_firing(self) -> bool:
        """检查是否正在射击"""
        return self._is_firing
