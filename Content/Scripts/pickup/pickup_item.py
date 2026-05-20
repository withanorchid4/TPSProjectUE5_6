# -*- encoding: utf-8 -*-
"""
拾取道具 Actor - 敌人死亡时掉落

功能:
- 两种类型：弹药包 / 急救包
- 碰撞检测（Overlap）拾取
- RotatingMovementComponent 旋转
- SetLifeSpan 超时消失
"""

import ue

_next_item_uid = 1


@ue.uclass()
class PickupItem(ue.Actor):
    """敌人掉落的拾取物"""

    TYPE_AMMO = "ammo"
    TYPE_HEALTH = "health"

    AMMO_REFILL = 30            # 弹药包补充弹药数
    HP_REFILL = 50              # 急救包补充血量
    ROTATION_YAW_SPEED = 90.0   # 旋转速度（度/秒）
    LIFETIME = 15.0             # 自动消失时间（秒）

    # 模型路径
    AMMO_MESH_PATH = "/Game/Weapons/supply_crates-Vicevoxel-FBX/VV_ammobox_001.VV_ammobox_001"
    HEALTH_MESH_PATH = "/Game/Weapons/supply_crates-Vicevoxel-FBX/VV_aidbox_001.VV_aidbox_001"

    def __init_pyobj__(self):
        global _next_item_uid
        self.collision_sphere = None
        self.pickup_mesh = None
        self.pickup_type = None  # 在 ReceiveBeginPlay 中随机决定
        self.item_uid = _next_item_uid
        _next_item_uid += 1

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        spawn_loc = self.GetActorLocation()
        spawn_rot = self.GetActorRotation()

        # 50% 弹药 / 50% 血包
        self.pickup_type = self.TYPE_AMMO if ue.KismetMathLibrary.RandomFloat() < 0.5 else self.TYPE_HEALTH

        # 超时自动销毁
        self.SetLifeSpan(self.LIFETIME)

        # 碰撞球
        self.collision_sphere = ue.NewObject(ue.SphereComponent, self, "CollisionSphere")
        self.collision_sphere.RegisterComponent()
        self.collision_sphere.SetSphereRadius(80.0)
        self.collision_sphere.SetCollisionProfileName(ue.Name("OverlapAllDynamic"))
        self.SetRootComponent(self.collision_sphere)

        # 视觉模型：根据类型选择
        self.pickup_mesh = ue.NewObject(ue.StaticMeshComponent, self, "PickupMesh")
        self.pickup_mesh.RegisterComponent()
        self.pickup_mesh.SetCollisionEnabled(0)  # NoCollision

        mesh_path = self.AMMO_MESH_PATH if self.pickup_type == self.TYPE_AMMO else self.HEALTH_MESH_PATH
        static_mesh = ue.LoadObject(ue.StaticMesh, mesh_path)
        if static_mesh:
            self.pickup_mesh.SetStaticMesh(static_mesh)
            # 补偿模型原点偏移，让视觉中心对齐 root（避免旋转时公转）
            box = static_mesh.GetBoundingBox()
            if box:
                center = box.Min + (box.Max - box.Min) * 0.5
                self.pickup_mesh.SetRelativeLocation(
                    ue.Vector(-center.X, -center.Y, -center.Z), False
                )

        scale = ue.Vector(1.0, 1.0, 1.0)
        self.pickup_mesh.SetWorldScale3D(scale)
        self.pickup_mesh.AttachToComponent(
            self.collision_sphere,
            ue.Name("None"),
            ue.EAttachmentRule.KeepRelative,
            ue.EAttachmentRule.KeepRelative,
            ue.EAttachmentRule.KeepRelative,
            False
        )

        # 自动旋转组件
        self.rotating_movement = ue.NewObject(ue.RotatingMovementComponent, self, "RotatingMovement")
        self.rotating_movement.RegisterComponent()
        self.rotating_movement.RotationRate = ue.Rotator(0.0, self.ROTATION_YAW_SPEED, 0.0)

        # 恢复位置 + 稍微抬高
        self.SetActorLocation(ue.Vector(spawn_loc.X, spawn_loc.Y, spawn_loc.Z + 20.0), False, False)
        self.SetActorRotation(spawn_rot, False)

        # 绑定碰撞
        self.OnActorBeginOverlap.Add(self._on_overlap)

        ue.LogWarning(f"PickupItem: Spawned {self.pickup_type} at ({spawn_loc.X:.0f},{spawn_loc.Y:.0f},{spawn_loc.Z:.0f})")

    def _on_overlap(self, overlapped_actor, other_actor):
        """玩家碰触拾取"""
        if not other_actor:
            return

        shooting = getattr(other_actor, 'shooting', None)
        health = getattr(other_actor, 'health', None)

        if not shooting or not health or health.is_dead():
            return

        if self.pickup_type == self.TYPE_AMMO:
            shooting.add_ammo(self.AMMO_REFILL)
            ue.LogWarning(f"PickupItem: {other_actor} picked up +{self.AMMO_REFILL} ammo")
        else:
            actual = health.heal(self.HP_REFILL)
            ue.LogWarning(f"PickupItem: {other_actor} picked up +{actual:.0f} HP")

        # 通知网络其他客户端销毁该道具
        net_manager = getattr(other_actor, '_net_manager', None)
        if net_manager:
            net_manager.send_pickup(self.item_uid)

        self.Destroy()

    def set_type(self, pickup_type):
        """覆盖道具类型（网络同步用，SpawnActor后调用）"""
        if self.pickup_type == pickup_type:
            return  # 类型一致，无需修改

        self.pickup_type = pickup_type

        # 更新视觉模型
        if self.pickup_mesh:
            mesh_path = self.AMMO_MESH_PATH if pickup_type == self.TYPE_AMMO else self.HEALTH_MESH_PATH
            static_mesh = ue.LoadObject(ue.StaticMesh, mesh_path)
            if static_mesh:
                self.pickup_mesh.SetStaticMesh(static_mesh)
                box = static_mesh.GetBoundingBox()
                if box:
                    center = box.Min + (box.Max - box.Min) * 0.5
                    self.pickup_mesh.SetRelativeLocation(
                        ue.Vector(-center.X, -center.Y, -center.Z), False
                    )
