# -*- encoding: utf-8 -*-
"""远程玩家实体（速度驱动 + 位置纠偏）

采用 KBEngine 风格的状态同步：
- 服务端广播 速度(vel_x/vel_z) + 位置，客户端用 AddMovementInput 驱动移动
- Walking 模式下 Velocity/动画/重力/碰撞全部自然工作
- 收到服务端位置时插值趋近（小偏差平滑，大偏差瞬移）
"""

import ue


# ─── 纠偏参数 ───
SNAP_DISTANCE = 500.0      # 超过此距离直接传送
INTERP_DISTANCE = 50.0      # 超过此距离开始插值纠偏
INTERP_SPEED = 10.0        # 插值速度（越大越快趋近服务端位置）
ROT_SPEED = 720.0           # 旋转追踪速度 (度/秒)

# ─── 速度驱动参数 ───
WALK_SPEED = 600.0
JOG_SPEED = 900.0


@ue.uclass()
class RemotePlayer(ue.Character):
    """远程玩家 Actor

    由 BaseCharacter 在收到 ScPlayerJoin 时 spawn，
    由 ScPlayerStates 驱动：速度驱动移动 + 位置插值纠偏。
    """

    # 蓝图路径
    BP_PATH = "/Game/BluePrint/BP_RemotePlayer.BP_RemotePlayer_C"

    def __init_pyobj__(self):
        self._player_id = -1
        self._char_name = ""
        self._weapon_mesh = None
        self._destroyed = False
        self._ticker_handle = None

        # 服务端目标位置（用于纠偏）
        self._server_loc = None   # {"x","y","z"}
        self._server_rot = None   # {"pitch","yaw","roll"}

        # 服务端速度
        self._vel_x = 0.0
        self._vel_z = 0.0

        # 动画变量
        self._anim_sprinting = False
        self._anim_aiming = False
        self._anim_reloading = False
        self._anim_weapon_drawn = False
        self._anim_in_air = False

        # 首次定位标记
        self._initial_placed = False

        # 追踪活跃的视觉魔法箭 {arrow_id: MagicArrow}
        self._active_arrows = {}

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        ue.Log(f"RemotePlayer: ReceiveBeginPlay (pid={self._player_id})")

    def setup(self, player_id, char_name):
        """初始化远程玩家"""
        self._player_id = player_id
        self._char_name = char_name

        # Walking 模式：自然移动/重力/碰撞/动画
        try:
            movement = self.CharacterMovement
            if movement:
                movement.bOrientRotationToMovement = False
                movement.MaxWalkSpeed = JOG_SPEED
        except Exception as e:
            ue.LogWarning(f"RemotePlayer: Failed to set Walking mode: {e}")

        # 挂载武器网格
        self._setup_weapon_mesh()

        # 启动 ticker
        self._ticker_handle = ue.AddTicker(self._on_ticker)

        ue.LogWarning(f"RemotePlayer: setup pid={player_id} name={char_name}")

    def _setup_weapon_mesh(self):
        """挂载武器网格到 hand_r socket"""
        mesh = self.GetMesh()
        if not mesh:
            return

        self._weapon_mesh = ue.NewObject(ue.StaticMeshComponent, self, "WeaponMesh")
        self._weapon_mesh.RegisterComponent()

        rifle_mesh = ue.LoadObject(ue.StaticMesh, "/Game/Weapons/Meshes/AR4/SM_AR4.SM_AR4")
        if rifle_mesh:
            self._weapon_mesh.SetStaticMesh(rifle_mesh)

        self._weapon_mesh.AttachToComponent(
            mesh,
            ue.Name("hand_r"),
            ue.EAttachmentRule.KeepRelative,
            ue.EAttachmentRule.KeepRelative,
            ue.EAttachmentRule.KeepRelative,
            False
        )
        self._weapon_mesh.SetRelativeRotation(
            ue.Rotator(0.0, 90.0, 0.0), False
        )
        self._weapon_mesh.SetVisibility(False)

    def update_state(self, location, rotation, is_sprinting=False,
                     is_aiming=False, is_reloading=False,
                     is_weapon_drawn=False, is_in_air=False,
                     vel_x=0.0, vel_z=0.0):
        """由网络数据驱动：更新服务端位置/速度（不直接移动角色）"""
        if self._destroyed:
            return

        # 首次定位：直接跳到目标位置
        if not self._initial_placed:
            loc = ue.Vector(location["x"], location["y"], location["z"])
            rot = ue.Rotator(rotation["pitch"], rotation["yaw"], rotation["roll"])
            self.K2_SetActorLocation(loc, False, None)
            self.K2_SetActorRotation(rot, False)
            self._initial_placed = True

        self._server_loc = dict(location)
        self._server_rot = dict(rotation)

        self._anim_sprinting = is_sprinting
        self._anim_aiming = is_aiming
        self._anim_reloading = is_reloading
        self._anim_weapon_drawn = is_weapon_drawn
        self._anim_in_air = is_in_air

        self._vel_x = vel_x
        self._vel_z = vel_z

    def _on_ticker(self, delta_time):
        """每帧：速度驱动移动 + 位置纠偏"""
        if self._destroyed:
            return False

        if not self._initial_placed:
            return True

        # ── 1. 速度驱动：AddMovementInput ──
        self._apply_velocity_input(delta_time)

        # ── 2. 位置纠偏 ──
        self._correct_position(delta_time)

        # ── 3. 旋转追踪 ──
        self._update_rotation(delta_time)

        # ── 4. 推送动画变量 ──
        self._update_anim_vars()

        return True

    def _apply_velocity_input(self, delta_time):
        """用服务端速度驱动移动

        远程玩家没有 Controller，AddMovementInput 不生效，
        直接设置 CharacterMovement.Velocity。
        """
        movement = self.CharacterMovement
        if not movement:
            return

        speed_sq = self._vel_x * self._vel_x + self._vel_z * self._vel_z
        if speed_sq < 1.0:
            # 速度为零时清空水平速度（保留垂直分量给重力）
            vel = movement.Velocity
            movement.Velocity = ue.Vector(0.0, 0.0, vel.z if vel else 0.0)
            return

        speed = speed_sq ** 0.5
        # 服务端 vel_x = UE X, vel_z = UE Y (水平面)
        # 直接设置 Velocity，Walking 模式下 CharacterMovement 会据此移动
        vel = movement.Velocity
        movement.Velocity = ue.Vector(self._vel_x, self._vel_z, vel.z if vel else 0.0)

    def _correct_position(self, delta_time):
        """位置纠偏：小偏差插值，大偏差瞬移"""
        if self._server_loc is None:
            return

        current_loc = self.GetActorLocation()
        server_loc = ue.Vector(
            self._server_loc["x"],
            self._server_loc["y"],
            self._server_loc["z"]
        )

        delta = server_loc - current_loc
        dist = delta.Size()

        if dist > SNAP_DISTANCE:
            # ── 太远：直接传送 ──
            self.K2_SetActorLocation(server_loc, False, None)

        elif dist > INTERP_DISTANCE:
            # ── 中等偏差：插值趋近 ──
            interp_alpha = min(1.0, INTERP_SPEED * delta_time)
            new_loc = current_loc + delta * interp_alpha
            self.K2_SetActorLocation(new_loc, False, None)

        # else: 偏差小，不纠偏，让 AddMovementInput 自然移动

    def _update_rotation(self, delta_time):
        """旋转追踪"""
        if self._server_rot is None:
            return

        target_yaw = self._server_rot["yaw"]
        target_pitch = self._server_rot["pitch"]
        target_roll = self._server_rot["roll"]

        current_rot = self.GetActorRotation()

        yaw_diff = self._shortest_angle_diff(current_rot.yaw, target_yaw)
        pitch_diff = self._shortest_angle_diff(current_rot.pitch, target_pitch)
        roll_diff = self._shortest_angle_diff(current_rot.roll, target_roll)

        max_rot = ROT_SPEED * delta_time

        if abs(yaw_diff) > max_rot:
            yaw_diff = max_rot if yaw_diff > 0 else -max_rot
        if abs(pitch_diff) > max_rot:
            pitch_diff = max_rot if pitch_diff > 0 else -max_rot
        if abs(roll_diff) > max_rot:
            roll_diff = max_rot if roll_diff > 0 else -max_rot

        new_yaw = current_rot.yaw + yaw_diff
        new_pitch = current_rot.pitch + pitch_diff
        new_roll = current_rot.roll + roll_diff

        self.K2_SetActorRotation(
            ue.Rotator(new_pitch, new_yaw, new_roll), False
        )

    @staticmethod
    def _shortest_angle_diff(current, target):
        """计算最短角度差"""
        diff = target - current
        while diff > 180.0:
            diff -= 360.0
        while diff < -180.0:
            diff += 360.0
        return diff

    def _update_anim_vars(self):
        """推送动画变量到 AnimBP

        Walking 模式下 CharacterMovement 自然维护 Velocity，
        AnimBP 可直接读取，无需手动推送。
        """
        mesh = self.GetMesh()
        if not mesh:
            return

        # 武器可见性跟随持枪状态
        if hasattr(self, '_weapon_mesh') and self._weapon_mesh:
            self._weapon_mesh.SetVisibility(self._anim_weapon_drawn)

        try:
            abp = mesh.GetAnimInstance()
            if not abp:
                return

            # Walking 模式下 Velocity 由 CharacterMovement 自然维护
            # AnimBP 从 Velocity 自动算出 Speed/Direction
            # 只需推送状态 bool
            if hasattr(abp, 'bIsSprinting'):
                abp.bIsSprinting = self._anim_sprinting
            if hasattr(abp, 'bIsAiming'):
                abp.bIsAiming = self._anim_aiming
            if hasattr(abp, 'bIsReloading'):
                abp.bIsReloading = self._anim_reloading
            if hasattr(abp, 'bHasWeapon'):
                abp.bHasWeapon = self._anim_weapon_drawn
            if hasattr(abp, 'bIsInAir'):
                abp.bIsInAir = self._anim_in_air
        except Exception as e:
            ue.LogWarning(f"RemotePlayer: _update_anim_vars error: {e}")

    def play_shoot(self, weapon_type=0, hit_location=None, arrow_id=0):
        """远程玩家射击：用本地枪口 + 网络命中点 渲染特效"""
        if self._destroyed:
            return

        mesh = self.GetMesh()
        if not mesh:
            return

        world = self.GetWorld()
        if not world:
            return

        actor_rot = self.GetActorRotation()
        forward = ue.KismetMathLibrary.GetForwardVector(actor_rot)

        if weapon_type == 0:
            # 枪口位置：用远程玩家自己的 hand_r socket + 前方偏移
            hand_loc = mesh.GetSocketLocation(ue.Name("hand_r"))
            muzzle_loc = hand_loc + forward * 30.0

            # 命中点：来自网络广播，缺省则用前方远处
            if hit_location:
                target_loc = ue.Vector(hit_location["x"], hit_location["y"], hit_location["z"])
            else:
                target_loc = muzzle_loc + forward * 3000.0

            # 枪口火花特效
            particle = ue.LoadObject(ue.ParticleSystem, "/Game/StarterContent/Particles/P_Explosion.P_Explosion")
            if particle:
                ue.GameplayStatics.SpawnEmitterAtLocation(
                    world, particle, muzzle_loc,
                    ue.Rotator(0.0, 0.0, 0.0),
                    ue.Vector(0.2, 0.2, 0.2),
                    True
                )

            # 命中点爆炸特效
            if hit_location and particle:
                ue.GameplayStatics.SpawnEmitterAtLocation(
                    world, particle, target_loc,
                    ue.Rotator(0.0, 0.0, 0.0),
                    ue.Vector(0.3, 0.3, 0.3),
                    True
                )

            # 射击音效
            sound = ue.LoadObject(ue.SoundBase, "/Game/StarterContent/Audio/Fire01_Cue.Fire01_Cue")
            if sound:
                ue.GameplayStatics.PlaySoundAtLocation(
                    world, sound, muzzle_loc,
                    ue.Rotator(0.0, 0.0, 0.0),
                    0.6, 1.0, 0.0
                )

            # 视觉弹道：枪口 → 命中点
            from character.tracer_round import TracerRound
            tracer_dir = target_loc - muzzle_loc
            tracer_rot = ue.KismetMathLibrary.MakeRotFromX(tracer_dir)
            tracer = world.SpawnActor(TracerRound, muzzle_loc, tracer_rot)
            if tracer:
                tracer.set_target(target_loc)
        else:
            hand_loc = mesh.GetSocketLocation(ue.Name("hand_r"))
            spawn_loc = hand_loc + forward * 30.0

            # 命中点：来自网络广播
            if hit_location:
                target_loc = ue.Vector(hit_location["x"], hit_location["y"], hit_location["z"])
            else:
                target_loc = spawn_loc + forward * 5000.0

            # 方向：枪口 → 命中点
            arrow_dir = target_loc - spawn_loc
            arrow_rot = ue.KismetMathLibrary.MakeRotFromX(arrow_dir)

            from character.magic_arrow import MagicArrow
            arrow = world.SpawnActor(MagicArrow, spawn_loc, arrow_rot)
            if arrow:
                arrow._visual_only = True
                arrow.SetOwner(self)
                # SpawnActor 返回后立刻禁用碰撞，防止 on_tick 0.05s 后重新启用
                if hasattr(arrow, 'collision_sphere') and arrow.collision_sphere:
                    arrow.collision_sphere.SetCollisionEnabled(0)
                    arrow.collision_sphere.SetCollisionProfileName(ue.Name("NoCollision"))
                arrow._collision_activated = True
                if hasattr(arrow, 'set_target'):
                    arrow.set_target(target_loc)
                
                # 记录箭矢ID，用于后续命中时销毁
                arrow.arrow_id = arrow_id
                if arrow_id > 0:
                    self._active_arrows[arrow_id] = arrow

    def destroy_arrow(self, arrow_id):
        """根据 arrow_id 销毁对应的视觉魔法箭"""
        arrow = self._active_arrows.pop(arrow_id, None)
        if arrow:
            try:
                arrow._stop_ticker()
                arrow.Destroy()
            except Exception as e:
                ue.LogWarning(f"RemotePlayer: destroy_arrow error: {e}")

    def do_cleanup(self):
        """清理并销毁自身"""
        if self._destroyed:
            return
        self._destroyed = True
        
        # 清理所有活跃的视觉箭
        for aid, arrow in list(self._active_arrows.items()):
            try:
                arrow._stop_ticker()
                arrow.Destroy()
            except Exception:
                pass
        self._active_arrows.clear()
        
        if self._ticker_handle is not None:
            try:
                ue.RemoveTicker(self._ticker_handle)
            except Exception:
                pass
            self._ticker_handle = None
        ue.LogWarning(f"RemotePlayer: cleanup pid={self._player_id}")
        self.K2_DestroyActor()

    @ue.ufunction(override=True)
    def ReceiveEndPlay(self, end_play_reason):
        self._destroyed = True
        if self._ticker_handle is not None:
            try:
                ue.RemoveTicker(self._ticker_handle)
            except Exception:
                pass
            self._ticker_handle = None
