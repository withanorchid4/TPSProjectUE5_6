# -*- encoding: utf-8 -*-
"""射击组件"""

import ue


class ShootingComponent:
    """处理射击逻辑"""
    
    DEFAULT_FIRE_RATE = 0.1  # 射击间隔（秒）
    MUZZLE_OFFSET = ue.Vector(100.0, 0.0, 50.0)  # 枪口偏移
    
    def __init__(self, owner):
        """
        初始化射击组件
        
        Args:
            owner: 角色实例 (ue.Character)
        """
        self.owner = owner
        self.bullet_class = None
        self.fire_rate = self.DEFAULT_FIRE_RATE
        self.last_fire_time = -999.0
    
    def set_bullet_class(self, bullet_class):
        """
        设置子弹类
        
        Args:
            bullet_class: 子弹 Actor 类
        """
        self.bullet_class = bullet_class
        ue.Log(f"Bullet class set to: {bullet_class}")
    
    def can_shoot(self) -> bool:
        """检查是否可以射击"""
        if not self.bullet_class:
            return False
        
        current_time = ue.GetGameTimeInSeconds()
        return (current_time - self.last_fire_time) >= self.fire_rate
    
    def shoot(self):
        """执行射击"""
        if not self.can_shoot():
            return False
        
        # 获取射击位置和方向
        actor_location = self.owner.GetActorLocation()
        control_rotation = self.owner.GetControlRotation()
        
        # 计算枪口位置
        spawn_location = actor_location + self.MUZZLE_OFFSET
        
        # 生成子弹
        world = self.owner.GetWorld()
        bullet = world.SpawnActor(
            self.bullet_class,
            spawn_location,
            control_rotation
        )
        
        if bullet:
            self.last_fire_time = ue.GetGameTimeInSeconds()
            ue.Log(f"Shot fired at {spawn_location}")
            return True
        
        return False
    
    def get_fire_direction(self) -> ue.Vector:
        """获取射击方向"""
        rotation = self.owner.GetControlRotation()
        # 将旋转转换为方向向量
        return ue.RotationToVector(rotation)
