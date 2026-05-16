# -*- encoding: utf-8 -*-
"""魔法箭 — 命中后晕眩范围内敌人3秒"""

import ue
from system.tickable import TickableMixin


@ue.uclass()
class MagicArrow(ue.Actor, TickableMixin):
    """
    魔法箭 Actor
    
    箭矢飞行体 + 冰霜拖尾特效，命中后对范围内敌人晕眩3秒
    使用 TickableMixin (ue.AddTicker) 替代 ReceiveTick。
    """
    
    ARROW_SPEED = 3000.0
    ARROW_LIFETIME = 10.0
    MAX_FLIGHT_DISTANCE = 30000.0  # 10s * ARROW_SPEED
    STUN_RADIUS = 500.0       # 晕眩范围
    STUN_DURATION = 3.0        # 晕眩时长
    COLLISION_RADIUS = 50.0
    
    def __init_pyobj__(self):
        self.arrow_mesh = None
        self.collision_sphere = None
        self.projectile_movement = None
        self.trail_effect = None
        self.spawn_time = 0.0
        self._hit_time = -1.0
        self._destroy_timer = -1.0
        self._spawn_location = None
        self._ticker_handle = None
        self._collision_activated = False
        self._visual_only = False   # 纯视觉模式：禁用碰撞和命中逻辑
        self.arrow_id = 0           # 由 ShootingComponent 在发射时分配
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        spawn_loc = self.GetActorLocation()
        spawn_rot = self.GetActorRotation()
        
        self.spawn_time = self.GetGameTimeSinceCreation()
        self._spawn_location = spawn_loc
        self._setup_collision()
        self._setup_visual()
        self._setup_trail()
        
        self.SetActorLocation(spawn_loc, False, False)
        self.SetActorRotation(spawn_rot, False)
        
        self._setup_movement()
        self.OnActorBeginOverlap.Add(self._on_overlap)
        self.OnActorHit.Add(self._on_hit)
        
        # 启动 ticker（替代 ReceiveTick）
        self._start_ticker()
        
        forward = ue.KismetMathLibrary.GetForwardVector(spawn_rot)
        ue.LogWarning(f"MagicArrow: Spawned at ({spawn_loc.X:.0f},{spawn_loc.Y:.0f},{spawn_loc.Z:.0f})")
    
    def _setup_collision(self):
        self.collision_sphere = ue.NewObject(
            ue.SphereComponent, self, "CollisionSphere"
        )
        self.collision_sphere.RegisterComponent()
        self.collision_sphere.SetSphereRadius(self.COLLISION_RADIUS)
        self.collision_sphere.SetCollisionProfileName(ue.Name("BlockAll"))
        self.collision_sphere.IgnoreActorWhenMoving(self.GetOwner(), True)
        # 纯视觉模式直接禁用碰撞，否则延迟0.05秒后开启
        if self._visual_only:
            self.collision_sphere.SetCollisionEnabled(0)
            self._collision_activated = True
        else:
            self.collision_sphere.SetCollisionEnabled(0)
        self.SetRootComponent(self.collision_sphere)
    
    def _setup_visual(self):
        self.arrow_mesh = ue.NewObject(
            ue.StaticMeshComponent, self, "ArrowMesh"
        )
        self.arrow_mesh.RegisterComponent()
        # 先禁用碰撞再设网格，避免默认碰撞干扰根碰撞球
        self.arrow_mesh.SetCollisionEnabled(0)  # NoCollision
        
        cylinder = ue.LoadObject(ue.StaticMesh, "/Engine/BasicShapes/Cylinder.Cylinder")
        if cylinder:
            self.arrow_mesh.SetStaticMesh(cylinder)
        
        # 圆柱体默认沿Z轴，-90° pitch 让它沿X轴（前方）
        self.arrow_mesh.SetRelativeRotation(ue.Rotator(-90.0, 0.0, 0.0))
        self.arrow_mesh.SetWorldScale3D(ue.Vector(0.15, 0.15, 1.2))
        
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
    
    def _setup_trail(self):
        """挂载冰霜拖尾 Niagara 特效"""
        self.trail_effect = ue.NewObject(
            ue.NiagaraComponent, self, "TrailEffect"
        )
        self.trail_effect.RegisterComponent()
        
        trail_system = ue.LoadObject(
            ue.NiagaraSystem,
            "/Game/ArrowTrail/FX/NS_ArrowTrail_Magic.NS_ArrowTrail_Magic"
        )
        if trail_system:
            self.trail_effect.SetAsset(trail_system)
            self.trail_effect.SetWorldScale3D(ue.Vector(1.0, 1.0, 1.0))
        else:
            ue.LogWarning("MagicArrow: Trail Niagara system not found!")
        
        if self.collision_sphere:
            self.trail_effect.AttachToComponent(
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
        self.projectile_movement.ProjectileGravityScale = 0.0
        
        forward = ue.KismetMathLibrary.GetForwardVector(self.GetActorRotation())
        self.projectile_movement.Velocity = forward * self.ARROW_SPEED
    
    # 类级别缓存，避免每次 LoadObject
    _aoe_system = None

    def _spawn_aoe_effect(self):
        """在命中位置生成 AOE 特效"""
        if MagicArrow._aoe_system is None:
            MagicArrow._aoe_system = ue.LoadObject(
                ue.NiagaraSystem,
                "/Game/Basic_VFX/Niagara/NS_Basic_6.NS_Basic_6"
            )
        if not MagicArrow._aoe_system:
            ue.LogWarning("MagicArrow: AOE Niagara system not found!")
            return

        hit_loc = self.GetActorLocation()
        aoe_comp = ue.NewObject(ue.NiagaraComponent, self, "AOEEffect")
        aoe_comp.RegisterComponent()
        aoe_comp.SetAsset(MagicArrow._aoe_system)
        aoe_comp.SetWorldLocationAndRotation(hit_loc, ue.Rotator(0, 0, 0), False, False)
        aoe_comp.bAutoDestroy = True
        aoe_comp.Activate(True)
        aoe_comp.SeekToDesiredAge(0.5)
        ue.Log("MagicArrow: AOE effect spawned")

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
    
    def _send_hit_to_server(self):
        """发送魔法箭命中事件到服务器"""
        if self._visual_only or self.arrow_id == 0:
            return
        try:
            from network.network_manager import NetworkManager
            nm = NetworkManager.get_instance()
            if nm.is_in_game:
                aoe_loc = self.GetActorLocation()
                nm.send_magic_arrow_hit(
                    arrow_id=self.arrow_id,
                    aoe_location={"x": aoe_loc.x, "y": aoe_loc.y, "z": aoe_loc.z}
                )
        except Exception as e:
            ue.LogError(f"MagicArrow: send_hit failed: {e}")
    
    def _on_overlap(self, overlapped_actor, other_actor):
        if not other_actor or self._visual_only:
            return
        # ue.LogWarning(f"MagicArrow: _on_overlap other={other_actor}")
        # 忽略 owner
        if other_actor == self.GetOwner():
            # ue.Log("MagicArrow: overlap ignored (owner)")
            return
        
        # 播放魔法命中音效
        owner = self.GetOwner()
        if owner and hasattr(owner, 'audio') and owner.audio:
            owner.audio.play_magic_arrow(self.GetActorLocation())
        
        # 命中任何东西 → 播放AOE特效 + 晕眩范围内敌人
        self._spawn_aoe_effect()
        self._stun_nearby_enemies()
        
        # 网络同步：广播魔法箭命中事件
        self._send_hit_to_server()
        
        self._start_destroy()
    
    def _on_hit(self, self_actor, other_actor, normal_impulse, hit_result):
        if not other_actor or self._visual_only:
            return
        # ue.LogWarning(f"MagicArrow: _on_hit other={other_actor}")
        if other_actor == self.GetOwner():
            # ue.Log("MagicArrow: hit ignored (owner)")
            return
        
        # 播放魔法命中音效
        owner = self.GetOwner()
        if owner and hasattr(owner, 'audio') and owner.audio:
            owner.audio.play_magic_arrow(self.GetActorLocation())
        
        # ue.LogWarning(f"MagicArrow: hit! spawning AOE + stun")
        self._spawn_aoe_effect()
        self._stun_nearby_enemies()
        
        # 网络同步：广播魔法箭命中事件
        self._send_hit_to_server()
        
        self._start_destroy()
    
    def _start_destroy(self):
        """隐藏箭矢模型和碰撞，启动2秒延迟销毁"""
        # ue.LogWarning(f"MagicArrow: _start_destroy, will destroy in 2s")
        if self.arrow_mesh:
            self.arrow_mesh.SetVisibility(False)
        if self.trail_effect:
            self.trail_effect.SetVisibility(False)
        if self.collision_sphere:
            self.collision_sphere.SetCollisionEnabled(0)  # NoCollision
        if self.projectile_movement:
            self.projectile_movement.Velocity = ue.Vector(0, 0, 0)
        self._destroy_timer = 2.0  # 2秒后销毁
    
    def on_tick(self, delta_time):
        """每帧更新（替代 ReceiveTick）"""
        # 延迟开启碰撞（0.05秒后），避免出生时撞到玩家自身
        # 纯视觉模式不开启碰撞
        if not self._collision_activated and not self._visual_only:
            if self.GetGameTimeSinceCreation() - self.spawn_time > 0.05:
                if self.collision_sphere:
                    self.collision_sphere.SetCollisionEnabled(3)  # QueryAndPhysics
                    # ue.LogWarning("MagicArrow: collision activated (BlockAll)")
                self._collision_activated = True
        
        # 命中后倒计时销毁
        if self._destroy_timer > 0:
            self._destroy_timer -= delta_time
            if self._destroy_timer <= 0:
                self._stop_ticker()
                self.Destroy()
            return
        # 超时销毁
        now = self.GetGameTimeSinceCreation()
        if now - self.spawn_time > self.ARROW_LIFETIME:
            self._stun_nearby_enemies()
            self._stop_ticker()
            self.Destroy()
            return
        # 超距销毁
        if self._spawn_location:
            dist = ue.KismetMathLibrary.VSize(self.GetActorLocation() - self._spawn_location)
            if dist > self.MAX_FLIGHT_DISTANCE:
                self._stop_ticker()
                self.Destroy()
