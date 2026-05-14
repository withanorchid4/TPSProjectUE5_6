# -*- encoding: utf-8 -*-
"""
子弹 Actor - 纯 Python 实现

功能:
- 发射后沿直线飞行
- Overlap 碰撞检测（无物理击退）
- 碰到敌人造成伤害，碰到墙壁销毁
"""

import ue


@ue.uclass()
class Bullet(ue.Actor):
    """
    子弹 Actor
    
    使用 SphereCollision 做碰撞检测，ProjectileMovementComponent 控制移动
    """
    
    # 子弹参数
    BULLET_SPEED = 3000.0        # 初始速度（调试：放慢）
    BULLET_LIFETIME = 5.0        # 生命周期（秒）
    BULLET_DAMAGE = 10.0         # 伤害值
    BULLET_SCALE_XY = 0.25       # 子弹粗细（调试：放大5倍）
    BULLET_SCALE_Z = 1.5         # 子弹长度
    COLLISION_RADIUS = 50.0      # 碰撞球半径（调试：放大）
    
    def __init_pyobj__(self):
        """初始化 Python 变量"""
        self.projectile_movement = None
        self.bullet_mesh = None
        self.collision_sphere = None
        self.spawn_time = 0.0
        self._owner_actor = None
        self.damage_multiplier = 1.0  # 由ShootingComponent在生成时设置
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        """Actor 开始播放时调用"""
        ue.Log(f"Bullet '{self}' ReceiveBeginPlay")
        
        # 保存生成位置（SetRootComponent 会冲掉初始 Transform）
        spawn_loc = self.GetActorLocation()
        spawn_rot = self.GetActorRotation()
        
        self.spawn_time = self.GetGameTimeSinceCreation()
        self._setup_collision()
        self._setup_visual()
        
        # 恢复生成位置
        self.SetActorLocation(spawn_loc, False, False)
        self.SetActorRotation(spawn_rot, False)
        
        self._setup_projectile_movement()
        
        # 绑定碰撞事件
        self.OnActorBeginOverlap.Add(self._on_overlap)
        self.OnActorHit.Add(self._on_hit)
        
        # 调试日志
        forward = ue.KismetMathLibrary.GetForwardVector(spawn_rot)
        ue.LogWarning(f"Bullet: Spawned at ({spawn_loc.X:.0f},{spawn_loc.Y:.0f},{spawn_loc.Z:.0f}) "
                      f"dir=({forward.X:.2f},{forward.Y:.2f},{forward.Z:.2f}) "
                      f"rot=({spawn_rot.Pitch:.1f},{spawn_rot.Yaw:.1f},{spawn_rot.Roll:.1f})")
    
    def _setup_collision(self):
        """设置碰撞球体作为根组件"""
        self.collision_sphere = ue.NewObject(
            ue.SphereComponent, self, "CollisionSphere"
        )
        self.collision_sphere.RegisterComponent()
        
        self.collision_sphere.SetSphereRadius(self.COLLISION_RADIUS)
        self.collision_sphere.SetCollisionProfileName(ue.Name("Projectile"))
        
        # 忽略 owner（玩家），避免生成时自己撞自己
        self.collision_sphere.IgnoreActorWhenMoving(self.GetOwner(), True)
        
        self.SetRootComponent(self.collision_sphere)
        
        ue.Log("Bullet: Collision setup complete")
    
    def _setup_visual(self):
        """设置视觉表现（静态网格）"""
        self.bullet_mesh = ue.NewObject(
            ue.StaticMeshComponent, self, "BulletMesh"
        )
        self.bullet_mesh.RegisterComponent()
        
        cylinder_mesh = ue.LoadObject(ue.StaticMesh, "/Engine/BasicShapes/Cylinder.Cylinder")
        if cylinder_mesh:
            self.bullet_mesh.SetStaticMesh(cylinder_mesh)
        
        self.bullet_mesh.SetWorldScale3D(ue.Vector(
            self.BULLET_SCALE_XY,
            self.BULLET_SCALE_XY,
            self.BULLET_SCALE_Z
        ))
        self.bullet_mesh.SetRelativeRotation(ue.Rotator(-90.0, 0.0, 0.0))
        self.bullet_mesh.SetCollisionEnabled(0)  # NoCollision，只用球体做碰撞
        
        if self.collision_sphere:
            self.bullet_mesh.AttachToComponent(
                self.collision_sphere,
                ue.Name("None"),
                ue.EAttachmentRule.KeepRelative,
                ue.EAttachmentRule.KeepRelative,
                ue.EAttachmentRule.KeepRelative,
                False
            )
        
        ue.Log("Bullet: Visual setup complete")
    
    def _setup_projectile_movement(self):
        """设置投射移动组件"""
        self.projectile_movement = ue.NewObject(
            ue.ProjectileMovementComponent, self, "ProjectileMovement"
        )
        self.projectile_movement.RegisterComponent()
        
        self.projectile_movement.InitialSpeed = self.BULLET_SPEED
        self.projectile_movement.MaxSpeed = self.BULLET_SPEED
        self.projectile_movement.bRotationFollowsVelocity = True
        self.projectile_movement.bShouldBounce = False
        self.projectile_movement.ProjectileGravityScale = 0.0
        
        forward = ue.KismetMathLibrary.GetForwardVector(self.GetActorRotation())
        self.projectile_movement.Velocity = forward * self.BULLET_SPEED
    
    def _on_overlap(self, overlapped_actor, other_actor):
        """Overlap 回调 — 对敌人造成伤害（无物理击退）"""
        if not other_actor:
            return
        
        # 忽略 owner
        owner = self.GetOwner()
        if other_actor == owner:
            return
        
        ue.LogWarning(f"Hahahahaha")

        # 只处理有 take_damage 的目标（敌人/玩家），跳过拾取物等
        if not hasattr(other_actor, 'take_damage'):
            return
        
        ue.LogWarning(f"Bullet: Overlapped with {other_actor}")
        final_damage = self.BULLET_DAMAGE * self.damage_multiplier
        other_actor.take_damage(final_damage, None)
        ue.LogWarning(f"Bullet: Hit {other_actor} for {final_damage:.1f} damage (x{self.damage_multiplier:.1f})")
        
        # 播放受击音效 + 爆炸特效
        owner = self.GetOwner()
        if owner and hasattr(owner, 'audio') and owner.audio:
            owner.audio.play_enemy_hit(self.GetActorLocation())
        
        self.Destroy()
    
    def _on_hit(self, self_actor, other_actor, normal_impulse, hit_result):
        """Hit 回调 — 碰到墙壁等静态物体时销毁"""
        if not other_actor:
            return
        
        # 忽略 owner
        owner = self.GetOwner()
        if other_actor == owner:
            return
        
        ue.Log(f"Bullet hit: {other_actor}")
        self.Destroy()
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        """每帧更新"""
        if self.GetGameTimeSinceCreation() - self.spawn_time > self.BULLET_LIFETIME:
            self.Destroy()
    
    @ue.ufunction(override=True)
    def ReceiveEndPlay(self, end_play_reason):
        """Actor 结束播放时调用"""
        pass