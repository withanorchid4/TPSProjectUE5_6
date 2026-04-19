# -*- encoding: utf-8 -*-
"""弹道轨迹弹丸 — 纯视觉，模拟 CS 风格的 tracer"""

import ue


@ue.uclass()
class TracerRound(ue.Actor):
    """
    CS 风格弹道轨迹弹丸
    
    从枪口高速飞向命中点，纯视觉不造成伤害。
    旋转由 bRotationFollowsVelocity 自动对齐飞行方向。
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

    def set_target(self, target_point):
        """设置目标点（命中点），用于到达后销毁"""
        self._target_point = target_point

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        spawn_loc = self.GetActorLocation()
        spawn_rot = self.GetActorRotation()

        self.spawn_time = self.GetGameTimeSinceCreation()

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

    def _setup_emissive_material(self):
        """给弹丸设置自发光材质"""
        if not self.tracer_mesh:
            return
        mat = ue.LoadObject(ue.Material, "/Engine/EngineMaterials/DefaultParticleMaterial.DefaultParticleMaterial")
        if mat:
            dyn_mat = self.tracer_mesh.CreateDynamicMaterialInstance(0, mat)
            if dyn_mat:
                try:
                    dyn_mat.SetVectorParameter(ue.Name("Color"), ue.LinearColor(1.0, 0.7, 0.0, 1.0))
                except Exception:
                    pass
        else:
            mat2 = ue.LoadObject(ue.Material, "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")
            if mat2:
                self.tracer_mesh.CreateDynamicMaterialInstance(0, mat2)

    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        if self.GetGameTimeSinceCreation() - self.spawn_time > self.MAX_LIFETIME:
            self.Destroy()
            return
        if self._target_point:
            diff = self._target_point + self.GetActorLocation() * -1.0
            if diff.Size() < 50.0:
                self.Destroy()