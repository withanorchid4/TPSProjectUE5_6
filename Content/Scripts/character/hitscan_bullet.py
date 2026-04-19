# -*- encoding: utf-8 -*-
"""HitScan 子弹 Actor - 高速隐形子弹，替代 LineTrace

NePy 的 HitResult 无法提取 Actor（ActorInstanceHandle/WeakPtr 无解引用方法），
因此用高速 Projectile + Overlap 回调实现瞬间命中检测。
速度设为 30000，约 1 帧即可飞完场景，体感等同于 HitScan。
"""

import ue


@ue.uclass()
class HitscanBullet(ue.Actor):
    """
    高速隐形子弹，用于 HitScan 射击
    
    - 速度极快（30000），1帧飞完场景
    - 无视觉网格（不可见）
    - Overlap 回调直接拿到 enemy actor
    - 碰到任何物体即销毁
    """

    BULLET_SPEED = 8000.0        # 高速但能触发overlap（~133单位/帧@60fps）
    BULLET_LIFETIME = 0.5        # 短生命周期
    COLLISION_RADIUS = 50.0      # 碰撞球半径（较大确保命中）

    def __init_pyobj__(self):
        self.collision_sphere = None
        self.projectile_movement = None
        self.spawn_time = 0.0
        self.damage = 10.0
        self.damage_multiplier = 1.0

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        spawn_loc = self.GetActorLocation()
        spawn_rot = self.GetActorRotation()

        self.spawn_time = self.GetGameTimeSinceCreation()

        # 碰撞球
        self.collision_sphere = ue.NewObject(
            ue.SphereComponent, self, "CollisionSphere"
        )
        self.collision_sphere.RegisterComponent()
        self.collision_sphere.SetSphereRadius(self.COLLISION_RADIUS)
        self.collision_sphere.SetCollisionProfileName(ue.Name("Projectile"))
        self.collision_sphere.IgnoreActorWhenMoving(self.GetOwner(), True)
        self.SetRootComponent(self.collision_sphere)

        # 恢复位置
        self.SetActorLocation(spawn_loc, False, False)
        self.SetActorRotation(spawn_rot, False)

        # 投射移动
        self.projectile_movement = ue.NewObject(
            ue.ProjectileMovementComponent, self, "ProjectileMovement"
        )
        self.projectile_movement.RegisterComponent()
        self.projectile_movement.InitialSpeed = self.BULLET_SPEED
        self.projectile_movement.MaxSpeed = self.BULLET_SPEED
        self.projectile_movement.bRotationFollowsVelocity = True
        self.projectile_movement.bShouldBounce = False
        self.projectile_movement.ProjectileGravityScale = 0.0
        forward = ue.KismetMathLibrary.GetForwardVector(spawn_rot)
        self.projectile_movement.Velocity = forward * self.BULLET_SPEED

        # 绑定碰撞
        self.OnActorBeginOverlap.Add(self._on_overlap)
        self.OnActorHit.Add(self._on_hit)

    def _on_overlap(self, overlapped_actor, other_actor):
        """Overlap 回调 — 命中敌人扣血"""
        if not other_actor:
            return
        if other_actor == self.GetOwner():
            return

        # 只处理有 take_damage 的目标
        if hasattr(other_actor, 'take_damage'):
            final_damage = self.damage * self.damage_multiplier
            other_actor.take_damage(final_damage, self.GetOwner())
            ue.Log(f"HitscanBullet: Hit {other_actor} for {final_damage:.1f} damage")

            # 命中特效
            owner = self.GetOwner()
            if owner and hasattr(owner, 'audio') and owner.audio:
                owner.audio.play_enemy_hit(self.GetActorLocation())

        self.Destroy()

    def _on_hit(self, self_actor, other_actor, normal_impulse, hit_result):
        """Hit 回调 — 碰到墙壁等静态物体时销毁"""
        if other_actor == self.GetOwner():
            return
        self.Destroy()

    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        if self.GetGameTimeSinceCreation() - self.spawn_time > self.BULLET_LIFETIME:
            self.Destroy()
