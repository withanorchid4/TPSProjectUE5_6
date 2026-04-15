# -*- encoding: utf-8 -*-
"""远程敌人子弹"""

import ue


@ue.uclass()
class EnemyProjectile(ue.Actor):
    """
    远程敌人发射的子弹
    
    速度较慢，碰到玩家造成伤害
    """
    
    PROJECTILE_SPEED = 1500.0
    PROJECTILE_LIFETIME = 5.0
    PROJECTILE_DAMAGE = 10.0
    BULLET_SCALE_XY = 0.15
    BULLET_SCALE_Z = 0.6
    COLLISION_RADIUS = 30.0
    
    def __init_pyobj__(self):
        self.bullet_mesh = None
        self.collision_sphere = None
        self.projectile_movement = None
        self.spawn_time = 0.0
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        # 保存生成位置
        spawn_loc = self.GetActorLocation()
        spawn_rot = self.GetActorRotation()
        
        self.spawn_time = self.GetGameTimeSinceCreation()
        self._setup_collision()
        self._setup_visual()
        
        # 恢复生成位置
        self.SetActorLocation(spawn_loc, False, False)
        self.SetActorRotation(spawn_rot, False)
        
        self._setup_movement()
        self.OnActorBeginOverlap.Add(self._on_overlap)
    
    def _setup_collision(self):
        self.collision_sphere = ue.NewObject(
            ue.SphereComponent, self, "CollisionSphere"
        )
        self.collision_sphere.RegisterComponent()
        self.collision_sphere.SetSphereRadius(self.COLLISION_RADIUS)
        self.collision_sphere.SetCollisionProfileName(ue.Name("Projectile"))
        # 忽略 owner，避免生成时撞到发射者
        self.collision_sphere.IgnoreActorWhenMoving(self.GetOwner(), True)
        self.SetRootComponent(self.collision_sphere)
    
    def _setup_visual(self):
        self.bullet_mesh = ue.NewObject(ue.StaticMeshComponent, self, "BulletMesh")
        self.bullet_mesh.RegisterComponent()
        
        cylinder = ue.LoadObject(ue.StaticMesh, "/Engine/BasicShapes/Cylinder.Cylinder")
        if cylinder:
            self.bullet_mesh.SetStaticMesh(cylinder)
        
        self.bullet_mesh.SetWorldScale3D(ue.Vector(
            self.BULLET_SCALE_XY,
            self.BULLET_SCALE_XY,
            self.BULLET_SCALE_Z
        ))
        self.bullet_mesh.SetRelativeRotation(ue.Rotator(-90.0, 0.0, 0.0))
        
        if self.collision_sphere:
            self.bullet_mesh.AttachToComponent(
                self.collision_sphere,
                ue.Name("None"),
                ue.EAttachmentRule.KeepRelative,
                ue.EAttachmentRule.KeepRelative,
                ue.EAttachmentRule.KeepRelative,
                False
            )
    
    def _setup_movement(self):
        self.projectile_movement = ue.NewObject(
            ue.ProjectileMovementComponent, self, "ProjectileMovement"
        )
        self.projectile_movement.RegisterComponent()
        
        self.projectile_movement.InitialSpeed = self.PROJECTILE_SPEED
        self.projectile_movement.MaxSpeed = self.PROJECTILE_SPEED
        self.projectile_movement.bRotationFollowsVelocity = True
        self.projectile_movement.bShouldBounce = False
        
        forward = ue.KismetMathLibrary.GetForwardVector(self.GetActorRotation())
        self.projectile_movement.Velocity = forward * self.PROJECTILE_SPEED
    
    def _on_overlap(self, overlapped_actor, other_actor):
        if not other_actor:
            return
        
        # 忽略 owner（发射者）
        if other_actor == self.GetOwner():
            return
        
        if hasattr(other_actor, 'take_damage'):
            other_actor.take_damage(self.PROJECTILE_DAMAGE, None)
            ue.Log(f"EnemyProjectile: Hit player for {self.PROJECTILE_DAMAGE}")
        
        self.Destroy()
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        if self.GetGameTimeSinceCreation() - self.spawn_time > self.PROJECTILE_LIFETIME:
            self.Destroy()