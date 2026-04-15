# -*- encoding: utf-8 -*-
"""魔法箭 — 命中后晕眩范围内敌人3秒"""

import ue


@ue.uclass()
class MagicArrow(ue.Actor):
    """
    魔法箭 Actor
    
    发光大圆柱飞行体，命中后对范围内敌人晕眩3秒
    """
    
    ARROW_SPEED = 2000.0
    ARROW_LIFETIME = 5.0
    STUN_RADIUS = 500.0       # 晕眩范围
    STUN_DURATION = 3.0        # 晕眩时长
    ARROW_SCALE_XY = 0.15      # 粗细
    ARROW_SCALE_Z = 0.6        # 长度
    COLLISION_RADIUS = 30.0
    
    def __init_pyobj__(self):
        self.arrow_mesh = None
        self.collision_sphere = None
        self.projectile_movement = None
        self.spawn_time = 0.0
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        spawn_loc = self.GetActorLocation()
        spawn_rot = self.GetActorRotation()
        
        self.spawn_time = self.GetGameTimeSinceCreation()
        self._setup_collision()
        self._setup_visual()
        
        self.SetActorLocation(spawn_loc, False, False)
        self.SetActorRotation(spawn_rot, False)
        
        self._setup_movement()
        self.OnActorBeginOverlap.Add(self._on_overlap)
        self.OnActorHit.Add(self._on_hit)
        
        forward = ue.KismetMathLibrary.GetForwardVector(spawn_rot)
        ue.LogWarning(f"MagicArrow: Spawned at ({spawn_loc.X:.0f},{spawn_loc.Y:.0f},{spawn_loc.Z:.0f})")
    
    def _setup_collision(self):
        self.collision_sphere = ue.NewObject(
            ue.SphereComponent, self, "CollisionSphere"
        )
        self.collision_sphere.RegisterComponent()
        self.collision_sphere.SetSphereRadius(self.COLLISION_RADIUS)
        self.collision_sphere.SetCollisionProfileName(ue.Name("Projectile"))
        self.collision_sphere.IgnoreActorWhenMoving(self.GetOwner(), True)
        self.SetRootComponent(self.collision_sphere)
    
    def _setup_visual(self):
        self.arrow_mesh = ue.NewObject(
            ue.StaticMeshComponent, self, "ArrowMesh"
        )
        self.arrow_mesh.RegisterComponent()
        
        cylinder = ue.LoadObject(ue.StaticMesh, "/Engine/BasicShapes/Cylinder.Cylinder")
        if cylinder:
            self.arrow_mesh.SetStaticMesh(cylinder)
        
        self.arrow_mesh.SetWorldScale3D(ue.Vector(
            self.ARROW_SCALE_XY,
            self.ARROW_SCALE_XY,
            self.ARROW_SCALE_Z
        ))
        self.arrow_mesh.SetRelativeRotation(ue.Rotator(-90.0, 0.0, 0.0))
        self.arrow_mesh.SetCollisionEnabled(0)  # NoCollision
        
        # 自发光材质
        glow_material = ue.LoadObject(ue.MaterialInterface, "/Game/Materials/Arrow/LightArrow.LightArrow")
        if glow_material:
            self.arrow_mesh.SetMaterial(0, glow_material)
        
        if self.collision_sphere:
            self.arrow_mesh.AttachToComponent(
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
        
        self.projectile_movement.InitialSpeed = self.ARROW_SPEED
        self.projectile_movement.MaxSpeed = self.ARROW_SPEED
        self.projectile_movement.bRotationFollowsVelocity = True
        self.projectile_movement.bShouldBounce = False
        
        forward = ue.KismetMathLibrary.GetForwardVector(self.GetActorRotation())
        self.projectile_movement.Velocity = forward * self.ARROW_SPEED
    
    def _stun_nearby_enemies(self):
        """晕眩范围内的敌人"""
        my_loc = self.GetActorLocation()
        
        # 查找所有 BaseEnemy 实例
        from enemy.base_enemy import BaseEnemy
        all_enemies = ue.GameplayStatics.GetAllActorsOfClass(
            self.GetWorld(), BaseEnemy
        )
        
        stunned_count = 0
        for enemy in all_enemies:
            dist = ue.KismetMathLibrary.VSize(enemy.GetActorLocation() - my_loc)
            if dist <= self.STUN_RADIUS and hasattr(enemy, 'ai') and enemy.ai:
                if not enemy.health.is_dead():
                    enemy.ai.set_stunned(self.STUN_DURATION)
                    stunned_count += 1
        
        ue.LogWarning(f"MagicArrow: Stunned {stunned_count} enemies in radius {self.STUN_RADIUS}")
    
    def _on_overlap(self, overlapped_actor, other_actor):
        if not other_actor:
            return
        
        # 忽略 owner
        if other_actor == self.GetOwner():
            return
        
        # 命中任何东西 → 晕眩范围内敌人
        self._stun_nearby_enemies()
        self.Destroy()
    
    def _on_hit(self, self_actor, other_actor, normal_impulse, hit_result):
        if not other_actor:
            return
        if other_actor == self.GetOwner():
            return
        
        self._stun_nearby_enemies()
        self.Destroy()
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        if self.GetGameTimeSinceCreation() - self.spawn_time > self.ARROW_LIFETIME:
            self._stun_nearby_enemies()
            self.Destroy()
