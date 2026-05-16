# -*- encoding: utf-8 -*-
"""弹道轨迹弹丸 — 纯视觉，模拟 CS 风格的 tracer"""

import ue
from system.tickable import TickableMixin


@ue.uclass()
class TracerRound(ue.Actor, TickableMixin):
    """
    CS 风格弹道轨迹弹丸
    
    从枪口高速飞向命中点，纯视觉不造成伤害。
    旋转由 bRotationFollowsVelocity 自动对齐飞行方向。
    使用 TickableMixin (ue.AddTicker) 替代 ReceiveTick。
    """

    TRACER_SPEED = 30000.0
    TRACER_SCALE_XY = 0.05
    TRACER_SCALE_Z = 1.5
    MAX_LIFETIME = 0.2

    def __init_pyobj__(self):
        self.tracer_mesh = None
        self.projectile_movement = None
        self.spawn_time = 0.0
        self._target_point = None
        self._ticker_handle = None
        self._spawn_location = None
        self._initial_dist_sq = 0.0

    def set_target(self, target_point):
        """设置目标点（命中点），用于到达后销毁"""
        self._target_point = target_point
        # 记录生成位置到目标的距离平方
        if self._spawn_location:
            diff = target_point + self._spawn_location * -1.0
            self._initial_dist_sq = diff.Size() * diff.Size()

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        spawn_loc = self.GetActorLocation()
        spawn_rot = self.GetActorRotation()

        self.spawn_time = self.GetGameTimeSinceCreation()
        self._spawn_location = spawn_loc

        # SceneComponent 做根，bRotationFollowsVelocity 控制根的朝向
        self._root_scene = ue.NewObject(
            ue.SceneComponent, self, "RootScene"
        )
        self._root_scene.RegisterComponent()
        self.SetRootComponent(self._root_scene)

        # 恢复位置
        self.SetActorLocation(spawn_loc, False, False)
        self.SetActorRotation(spawn_rot, False)

        # 创建细长圆柱体作为子组件，-90° pitch 让它沿X轴（前方）
        self.tracer_mesh = ue.NewObject(
            ue.StaticMeshComponent, self, "TracerMesh"
        )
        self.tracer_mesh.RegisterComponent()
        cylinder = ue.LoadObject(ue.StaticMesh, "/Engine/BasicShapes/Cylinder.Cylinder")
        if cylinder:
            self.tracer_mesh.SetStaticMesh(cylinder)
        else:
            ue.LogWarning("[TRACER] Cylinder mesh not found!")

        self.tracer_mesh.SetWorldScale3D(ue.Vector(
            self.TRACER_SCALE_XY,
            self.TRACER_SCALE_XY,
            self.TRACER_SCALE_Z
        ))
        self.tracer_mesh.SetCollisionEnabled(0)
        self.tracer_mesh.AttachToComponent(
            self._root_scene,
            ue.Name("None"),
            ue.EAttachmentRule.KeepRelative,
            ue.EAttachmentRule.KeepRelative,
            ue.EAttachmentRule.KeepRelative,
            False
        )
        # 圆柱体默认沿Z轴，-90° pitch 让它沿X轴（前方）
        # 作为子组件，RelativeRotation 相对于父（根），不会被 bRotationFollowsVelocity 覆盖
        self.tracer_mesh.SetRelativeRotation(ue.Rotator(-90.0, 0.0, 0.0), False)

        # 高速移动
        self.projectile_movement = ue.NewObject(
            ue.ProjectileMovementComponent, self, "ProjectileMovement"
        )
        self.projectile_movement.RegisterComponent()
        self.projectile_movement.InitialSpeed = self.TRACER_SPEED
        self.projectile_movement.MaxSpeed = self.TRACER_SPEED
        self.projectile_movement.bRotationFollowsVelocity = True
        self.projectile_movement.bShouldBounce = False
        self.projectile_movement.ProjectileGravityScale = 0.0

        forward = ue.KismetMathLibrary.GetForwardVector(spawn_rot)
        self.projectile_movement.Velocity = forward * self.TRACER_SPEED

        # 启动 ticker（替代 ReceiveTick）
        self._start_ticker()

    def on_tick(self, delta_time):
        """每帧更新（替代 ReceiveTick）"""
        if self.GetGameTimeSinceCreation() - self.spawn_time > self.MAX_LIFETIME:
            self._stop_ticker()
            self.Destroy()
            return
        if self._target_point and self._spawn_location:
            # 高速弹丸每帧移动 ~500 单位，距离判定 <50 会被跳过
            # 改用行程距离：已飞行距离² >= 起点到目标距离² → 已越过目标点
            diff_from_spawn = self.GetActorLocation() + self._spawn_location * -1.0
            traveled_sq = diff_from_spawn.Size() * diff_from_spawn.Size()
            if traveled_sq >= self._initial_dist_sq:
                self._stop_ticker()
                self.Destroy()
