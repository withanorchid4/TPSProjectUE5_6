# -*- encoding: utf-8 -*-
"""
子弹 Actor - 纯 Python 实现

功能:
- 发射后沿直线飞行
- 碰撞时销毁
- 包含视觉表现（静态网格）
"""

import ue


@ue.uclass()
class Bullet(ue.Actor):
    """
    子弹 Actor
    
    纯 Python 实现，使用 ProjectileMovementComponent 控制移动
    """
    
    # 子弹参数
    BULLET_SPEED = 15000.0       # 初始速度（cm/s）
    BULLET_LIFETIME = 2.0        # 生命周期（秒）
    BULLET_DAMAGE = 10.0         # 伤害值
    # 子弹缩放（参考5.56mm步枪弹，长径比约8:1）
    BULLET_SCALE_XY = 0.02       # 子弹粗细
    BULLET_SCALE_Z = 0.16        # 子弹长度（Z轴，旋转后朝前）
    
    def __init_pyobj__(self):
        """初始化 Python 变量"""
        self.projectile_movement = None
        self.bullet_mesh = None
        self.spawn_time = 0.0
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        """Actor 开始播放时调用"""
        ue.Log(f"Bullet '{self}' ReceiveBeginPlay")
        
        # 记录生成时间
        self.spawn_time = self.GetGameTimeSinceCreation()
        
        # 添加视觉表现
        self._setup_visual()
        
        # 设置投射移动组件
        self._setup_projectile_movement()
        
        # 绑定 Actor 级别的碰撞事件
        self.OnActorHit.Add(self._on_actor_hit)
    
    def _setup_visual(self):
        """设置视觉表现（静态网格）"""
        # 创建静态网格组件
        self.bullet_mesh = ue.NewObject(
            ue.StaticMeshComponent,
            self,
            "BulletMesh"
        )
        self.bullet_mesh.RegisterComponent()
        
        # 加载引擎自带的圆柱体网格
        cylinder_mesh = ue.LoadObject(ue.StaticMesh, "/Engine/BasicShapes/Cylinder.Cylinder")
        if cylinder_mesh:
            self.bullet_mesh.SetStaticMesh(cylinder_mesh)
        
        # 设置缩放（细长子弹）
        self.bullet_mesh.SetWorldScale3D(ue.Vector(
            self.BULLET_SCALE_XY,
            self.BULLET_SCALE_XY,
            self.BULLET_SCALE_Z
        ))
        
        # UE的Cylinder默认沿Z轴竖着，旋转-90度让子弹朝前（沿X轴飞行方向）
        self.bullet_mesh.SetRelativeRotation(
            ue.Rotator(-90.0, 0.0, 0.0)
        )
        
        # 附加到根组件（如果有的话）
        root = self.GetRootComponent()
        if root:
            self.bullet_mesh.AttachToComponent(
                root,
                ue.Name("None"),
                ue.EAttachmentRule.KeepRelative,
                ue.EAttachmentRule.KeepRelative,
                ue.EAttachmentRule.KeepRelative,
                False
            )
        else:
            # 如果没有根组件，设置为根组件
            self.bullet_mesh.SetupAttachment(None)
        
        ue.Log("Bullet: Visual setup complete")
    
    def _setup_projectile_movement(self):
        """设置投射移动组件"""
        # 查找现有的 ProjectileMovementComponent
        self.projectile_movement = self.GetComponentByClass(ue.ProjectileMovementComponent)
        
        if not self.projectile_movement:
            # 创建新的投射移动组件
            self.projectile_movement = ue.NewObject(
                ue.ProjectileMovementComponent,
                self,
                "ProjectileMovement"
            )
            self.projectile_movement.RegisterComponent()
        
        # 配置投射参数
        self.projectile_movement.InitialSpeed = self.BULLET_SPEED
        self.projectile_movement.MaxSpeed = self.BULLET_SPEED
        self.projectile_movement.bRotationFollowsVelocity = True
        self.projectile_movement.bShouldBounce = False
        
        # 根据 Actor 旋转设置初始速度方向
        actor_rotation = self.GetActorRotation()
        forward = ue.KismetMathLibrary.GetForwardVector(actor_rotation)
        self.projectile_movement.Velocity = forward * self.BULLET_SPEED
    
    def _on_actor_hit(self, self_actor, other_actor, normal_impulse, hit_result):
        """
        Actor 碰撞回调
        
        Args:
            self_actor: 自己
            other_actor: 碰撞到的 Actor
            normal_impulse: 冲击力
            hit_result: 命中结果
        """
        # 忽略碰撞到空（比如刚刚发射时的空气）
        if not other_actor:
            return
        
        ue.Log(f"Bullet hit: {other_actor}")
        
        # 这里可以添加伤害逻辑
        # if other_actor and hasattr(other_actor, 'take_damage'):
        #     other_actor.take_damage(self.BULLET_DAMAGE)
        
        # 销毁子弹
        self.Destroy()
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        """每帧更新"""
        # 检查生命周期
        current_time = self.GetGameTimeSinceCreation()
        if current_time - self.spawn_time > self.BULLET_LIFETIME:
            ue.Log(f"Bullet lifetime expired, destroying")
            self.Destroy()
    
    @ue.ufunction(override=True)
    def ReceiveEndPlay(self, end_play_reason):
        """Actor 结束播放时调用"""
        ue.Log(f"Bullet '{self}' ReceiveEndPlay")