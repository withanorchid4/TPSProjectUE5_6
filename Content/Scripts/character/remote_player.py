# -*- encoding: utf-8 -*-
"""远程玩家实体

在本地客户端场景中代表一个远程玩家，由网络数据驱动位置/旋转/动画。
"""

import ue
import time


@ue.uclass()
class RemotePlayer(ue.Character):
    """远程玩家 Actor

    由 BaseCharacter 在收到 ScPlayerJoin 时 spawn，
    由 ScPlayerStates 驱动位置更新。
    """

    # 蓝图路径（用户需要创建 BP_RemotePlayer 蓝图）
    BP_PATH = "/Game/BluePrint/BP_RemotePlayer.BP_RemotePlayer_C"

    def __init_pyobj__(self):
        self._player_id = -1
        self._char_name = ""
        self._last_location = None  # {"x","y","z"}
        self._last_update_time = 0.0
        self._weapon_mesh = None
        self._destroyed = False

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        ue.Log(f"RemotePlayer: ReceiveBeginPlay (pid={self._player_id})")

    def setup(self, player_id, char_name):
        """初始化远程玩家：挂载武器、设置名称"""
        self._player_id = player_id
        self._char_name = char_name

        # 关闭旋转跟随移动
        try:
            movement = self.CharacterMovement
            if movement:
                movement.bOrientRotationToMovement = False
        except Exception:
            pass

        # 挂载武器网格（和 BaseCharacter 一样）
        self._setup_weapon_mesh()

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
        self._weapon_mesh.SetVisibility(True)

    def update_state(self, location, rotation, is_sprinting=False,
                     is_aiming=False, is_reloading=False):
        """由网络数据驱动：更新位置/旋转/动画

        Args:
            location: {"x","y","z"}
            rotation: {"pitch","yaw","roll"}
            is_sprinting: 是否冲刺
            is_aiming: 是否瞄准
            is_reloading: 是否换弹
        """
        if self._destroyed:
            return

        new_loc = ue.Vector(location["x"], location["y"], location["z"])
        new_rot = ue.Rotator(rotation["pitch"], rotation["yaw"], rotation["roll"])

        # 计算速度供动画蓝图使用
        movement = self.CharacterMovement
        if movement and self._last_location:
            now = time.time()
            dt = now - self._last_update_time
            if dt > 0.001:
                dx = location["x"] - self._last_location["x"]
                dy = location["y"] - self._last_location["y"]
                dz = location["z"] - self._last_location["z"]
                speed = (dx * dx + dy * dy + dz * dz) ** 0.5 / dt
                forward = ue.KismetMathLibrary.GetForwardVector(new_rot)
                vel = forward * speed
                movement.Velocity = vel

        self._last_location = dict(location)
        self._last_update_time = time.time()

        # 移动 Actor
        self.K2_SetActorLocation(new_loc, False, None)
        self.K2_SetActorRotation(new_rot, False)

        # 更新动画蓝图变量
        mesh = self.GetMesh()
        if mesh:
            try:
                abp = mesh.GetAnimInstance()
                if abp:
                    if hasattr(abp, 'bIsSprinting'):
                        abp.bIsSprinting = is_sprinting
                    if hasattr(abp, 'bIsAiming'):
                        abp.bIsAiming = is_aiming
                    if hasattr(abp, 'bIsReloading'):
                        abp.bIsReloading = is_reloading
            except Exception:
                pass

    def play_shoot(self, weapon_type=0):
        """远程玩家射击：生成弹道特效

        Args:
            weapon_type: 0=普通子弹, 1=魔法箭
        """
        if self._destroyed:
            return

        mesh = self.GetMesh()
        if not mesh:
            return

        actor_loc = self.GetActorLocation()
        actor_rot = self.GetActorRotation()
        forward = ue.KismetMathLibrary.GetForwardVector(actor_rot)

        if weapon_type == 0:
            # 普通子弹：生成 TracerRound
            hand_loc = mesh.GetSocketLocation(ue.Name("hand_r"))
            muzzle_loc = hand_loc + forward * 30.0
            target_loc = actor_loc + forward * 3000.0

            from character.tracer_round import TracerRound
            world = self.GetWorld()
            if world:
                tracer_dir = target_loc - muzzle_loc
                tracer_rot = ue.KismetMathLibrary.MakeRotFromX(tracer_dir)
                tracer = world.SpawnActor(TracerRound, muzzle_loc, tracer_rot)
                if tracer:
                    tracer.set_target(target_loc)

            # 音效
            try:
                from system.audio_manager import AudioManager
                AudioManager.play_sound_at(muzzle_loc, "/Game/Sounds/Gunshot")
            except Exception:
                pass
        else:
            # 魔法箭：生成 MagicArrow
            hand_loc = mesh.GetSocketLocation(ue.Name("hand_r"))
            spawn_loc = hand_loc + forward * 30.0

            from character.magic_arrow import MagicArrow
            world = self.GetWorld()
            if world:
                arrow = world.SpawnActor(MagicArrow, spawn_loc, actor_rot)
                if arrow:
                    target_loc = actor_loc + forward * 5000.0
                    if hasattr(arrow, 'set_target'):
                        arrow.set_target(target_loc)

    def do_cleanup(self):
        """清理并销毁自身"""
        if self._destroyed:
            return
        self._destroyed = True
        ue.LogWarning(f"RemotePlayer: cleanup pid={self._player_id}")
        self.K2_DestroyActor()

    @ue.ufunction(override=True)
    def ReceiveEndPlay(self, end_play_reason):
        self._destroyed = True
