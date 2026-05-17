# -*- encoding: utf-8 -*-
"""敌人基类"""

import ue
from system.health_component import HealthComponent
from system.enemy_ai_component import EnemyAIComponent, EnemyState, EnemyState


@ue.uclass()
class BaseEnemy(ue.Character):
    """
    敌人基类，使用组件组合模式
    
    子类需重写:
        _create_ai_component() — 配置AI参数
        attack()                — 攻击逻辑
    """
    
    DEFAULT_MAX_HP = 100.0
    DEATH_MONTAGE_PATH = "/Game/Characters/Mannequins/Anims/Death/MM_Death_Front_03_Montage.MM_Death_Front_03_Montage"
    
    def __init_pyobj__(self):
        self.health = None
        self.ai = None
        self._death_timer = 0.0
        self._pending_hit_reset = False
        self._is_stunned = False
        self._target_yaw = None       # 目标朝向（平滑旋转用）
        self._rotation_speed = 15.0    # 旋转插值速度
        self._is_enemy = True         # 标记：供其他系统识别敌人
        
        # 网络同步
        self.enemy_id = 0             # 由主机分配的唯一ID
        self._is_network_driven = False  # 非主机时由网络驱动，禁用本地AI
        self._net_ai_state = 0        # 网络AI状态: 0=idle,1=chase,2=attack,3=stunned,4=dead
        self._net_is_attacking = False
        self._prev_net_ai_state = 0   # 上一帧网络AI状态（检测变化）
        self._prev_net_is_attacking = False
        self._prev_net_loc = None     # 上一帧网络位置（计算速度用）
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        ue.Log(f"{self} ReceiveBeginPlay")
        
        # 初始化血量组件
        self.health = HealthComponent(self, self.DEFAULT_MAX_HP)
        self.health.on_death = self._on_death
        self.health.on_damage = self._on_damage
        
        # 初始化AI组件
        self.ai = self._create_ai_component()
        self.ai.on_chase = self._on_chase
        self.ai.on_attack = self._on_attack
        self.ai.on_stop = self._on_stop
        self.ai.on_stunned = self._on_stunned
        self.ai.on_stun_end = self._on_stun_end
        
        # 角色配置
        self.bUseControllerRotationYaw = False
        
        # 敌人默认持枪
        self._setup_weapon()
        
        # 死亡计时器
        self._death_timer = 0.0
        
        ue.Log(f"BaseEnemy: Initialized ({self.__class__.__name__})")
    
    def _create_ai_component(self) -> EnemyAIComponent:
        """子类重写以配置AI参数"""
        return EnemyAIComponent(self)
    
    def take_damage(self, amount: float, attacker=None):
        """受到伤害"""
        if self.health and not self.health.is_dead():
            self.health.take_damage(amount, attacker)
    
    def attack(self):
        """子类重写以实现攻击逻辑"""
        pass
    
    def _on_death(self):
        """死亡回调"""
        self.ai.set_dead()

        # 通知 GameMode 敌人死亡
        from system.game_mode import _instance as game_mode
        if game_mode and hasattr(game_mode, 'on_enemy_killed'):
            game_mode.on_enemy_killed()

        self.SetActorEnableCollision(False)
        self._death_timer = 1.0  # 默认销毁时间，Montage播放成功后会覆盖
        
        # 播放死亡音效 + 爆炸特效（通过玩家AudioManager）
        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if pc:
            pawn = pc.GetPawn()
            if pawn and hasattr(pawn, 'audio') and pawn.audio:
                pawn.audio.play_enemy_death(self.GetActorLocation())
        
        # 播放死亡 Montage
        mesh = self.GetMesh()
        if mesh:
            anim = mesh.GetAnimInstance()
            if anim:
                death_montage = ue.LoadObject(ue.AnimMontage, self.DEATH_MONTAGE_PATH)
                if death_montage:
                    result = anim.Montage_Play(death_montage, 1.0)
                    # 死亡动画播到70%时销毁，避开末尾blend-out过渡
                    self._death_timer = result * 0.7
                    ue.LogWarning(f"BaseEnemy: Montage_Play result={result}")
                else:
                    ue.LogWarning(f"BaseEnemy: Death montage not found at {self.DEATH_MONTAGE_PATH}")
        
        # 停止移动
        movement = self.CharacterMovement
        if movement:
            movement.StopMovementImmediately()
        
        ue.Log(f"BaseEnemy: {self} died")
    
    def _on_damage(self, amount: float, attacker=None):
        """受伤回调 — 推送 bIsHit 脉冲 + 伤害跳字"""
        mesh = self.GetMesh()
        if mesh:
            anim = mesh.GetAnimInstance()
            if anim:
                anim.bIsHit = True
        
        # 通知 HUD 显示伤害跳字
        self._show_damage_number(amount)
        ue.Log(f"BaseEnemy: {self} took {amount} damage, HP={self.health.current_hp:.0f}")
    
    def _on_chase(self):
        """追击回调 — 向玩家移动"""
        if self._is_stunned:
            return
        player = self.ai._find_player()
        if not player:
            return
        
        direction = player.GetActorLocation() - self.GetActorLocation()
        direction.Z = 0.0
        length = ue.KismetMathLibrary.VSize(direction)
        if length > 0.0:
            direction = direction / length
        
        self.AddMovementInput(direction, 1.0)
        self._face_target(player)
    
    def _on_attack(self):
        """攻击回调"""
        player = self.ai._find_player()
        if player:
            self._face_target(player)
        self.attack()
    
    def _on_stop(self):
        """停止移动"""
        # 恢复追击速度
        movement = self.CharacterMovement
        if movement:
            movement.MaxWalkSpeed = 600.0
    
    def _setup_weapon(self):
        """挂载武器网格并设置持枪动画"""
        mesh = self.GetMesh()
        if not mesh:
            return
        
        # 推送 bHasWeapon = True 到 AnimBP
        anim = mesh.GetAnimInstance()
        if anim:
            anim.bHasWeapon = True
        
        # 挂载武器网格
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
        self._weapon_mesh.SetRelativeRotation(ue.Rotator(0.0, 90.0, 0.0), False)
    
    def _on_stunned(self):
        """晕眩开始 — 冻结动画"""
        self._is_stunned = True
        mesh = self.GetMesh()
        if mesh:
            mesh.GlobalAnimRateScale = 0.0
    
    def _on_stun_end(self):
        """晕眩结束 — 恢复动画"""
        self._is_stunned = False
        mesh = self.GetMesh()
        if mesh:
            mesh.GlobalAnimRateScale = 1.0
    
    def _face_target(self, target):
        """面向目标（设置目标朝向，由Tick平滑插值）"""
        direction = target.GetActorLocation() - self.GetActorLocation()
        if ue.KismetMathLibrary.VSize(direction) > 0.0:
            target_rotation = ue.KismetMathLibrary.MakeRotFromX(direction)
            self._target_yaw = target_rotation.Yaw
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        is_dead = self.health and self.health.is_dead()
        
        # 死亡后只做销毁倒计时
        if is_dead:
            self._death_timer -= delta_time
            if self._death_timer <= 0.0:
                self._spawn_pickup()
                self.Destroy()
            return
        
        # 网络驱动模式下不做本地AI/旋转
        if self._is_network_driven:
            # 只处理 bIsHit 还原
            mesh = self.GetMesh()
            if mesh:
                anim = mesh.GetAnimInstance()
                if anim:
                    if self._pending_hit_reset:
                        anim.bIsHit = False
                        self._pending_hit_reset = False
                    elif anim.bIsHit:
                        self._pending_hit_reset = True
            return
        
        # 更新AI
        if self.ai:
            self.ai.tick(delta_time)
        
        # 平滑旋转
        if self._target_yaw is not None and not self._is_stunned:
            current_rot = self.GetActorRotation()
            current_yaw = current_rot.Yaw
            diff = self._target_yaw - current_yaw
            if diff > 180.0:
                diff -= 360.0
            elif diff < -180.0:
                diff += 360.0
            new_yaw = current_yaw + diff * min(1.0, self._rotation_speed * delta_time)
            self.SetActorRotation(ue.Rotator(0.0, new_yaw, 0.0), False)
        
        # ATTACK 状态下持续面向玩家
        if self.ai and self.ai.state == EnemyState.ATTACK and not self._is_stunned:
            player = self.ai._find_player()
            if player:
                self._face_target(player)
        
        # 下一帧还原 bIsHit（延迟一帧，确保 AnimBP 能读到 True）
        mesh = self.GetMesh()
        if mesh:
            anim = mesh.GetAnimInstance()
            if anim:
                if self._pending_hit_reset:
                    anim.bIsHit = False
                    self._pending_hit_reset = False
                elif anim.bIsHit:
                    self._pending_hit_reset = True
    
    @ue.ufunction(override=True)
    def ReceiveEndPlay(self, end_play_reason):
        ue.Log(f"{self} ReceiveEndPlay")
    
    def _spawn_pickup(self):
        """死亡时50%概率生成弹药包/急救包"""
        from pickup.pickup_item import PickupItem
        loc = self.GetActorLocation()
        world = self.GetWorld()
        if world:
            pickup = world.SpawnActor(PickupItem, loc, ue.Rotator(0.0, 0.0, 0.0))
            if pickup:
                ue.Log(f"BaseEnemy: PickupItem spawned at ({loc.X:.0f},{loc.Y:.0f},{loc.Z:.0f})")
    
    def _show_damage_number(self, amount: float):
        """通知 HUD 显示伤害跳字"""
        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if pc:
            hud = pc.GetHUD()
            if hud and hasattr(hud, 'add_damage_number'):
                # 头顶偏移位置
                loc = self.GetActorLocation()
                head_pos = ue.Vector(loc.X, loc.Y, loc.Z + 180.0)
                hud.add_damage_number(head_pos, amount)
    
    def set_network_driven(self, enabled: bool):
        """设置网络驱动模式（非主机客户端调用）"""
        self._is_network_driven = enabled
        if enabled and self.ai:
            # 禁用本地AI：重置到IDLE
            self.ai.state = EnemyState.IDLE
    
    def apply_network_state(self, location, rotation, hp, ai_state, is_attacking):
        """应用网络状态（非主机客户端每帧调用）"""
        if not self._is_network_driven:
            return
        
        # 位置 + 旋转
        loc = ue.Vector(location["x"], location["y"], location["z"])
        rot = ue.Rotator(rotation.get("pitch", 0), rotation.get("yaw", 0), rotation.get("roll", 0))
        self.K2_SetActorLocation(loc, False, None)
        self.K2_SetActorRotation(rot, False)
        
        # 根据位置变化计算速度，驱动移动动画
        movement = self.CharacterMovement
        if movement:
            if self._prev_net_loc is not None:
                delta = loc - self._prev_net_loc
                # 用固定帧间隔估算速度（主机约60fps上报）
                vel = ue.Vector(delta.x * 60.0, delta.y * 60.0, delta.z * 60.0)
                movement.Velocity = vel
            self._prev_net_loc = loc
        
        # 血量同步
        if self.health and not self.health.is_dead():
            if hp <= 0:
                # 敌人在主机端已死但本地还活着 → 强制死亡
                self.take_damage(self.health.current_hp)
            elif hp < self.health.current_hp:
                # 血量减少（主机端已扣血） → 同步
                diff = self.health.current_hp - hp
                self.health.take_damage(diff)
        
        # AI状态 + 动画
        self._net_ai_state = ai_state
        self._net_is_attacking = is_attacking
        
        # 检测AI状态变化 → 推送动画
        if ai_state != self._prev_net_ai_state:
            self._apply_net_ai_state(ai_state)
            self._prev_net_ai_state = ai_state
        
        # 攻击动画
        if is_attacking and not self._prev_net_is_attacking:
            self.attack()
        self._prev_net_is_attacking = is_attacking
    
    def _apply_net_ai_state(self, ai_state):
        """根据网络AI状态推送本地表现"""
        mesh = self.GetMesh()
        if not mesh:
            return
        anim = mesh.GetAnimInstance()
        if not anim:
            return
        
        # ai_state: 0=idle, 1=chase, 2=attack, 3=stunned, 4=dead
        if ai_state == 3:  # STUNNED
            if not self._is_stunned:
                self._is_stunned = True
                mesh.GlobalAnimRateScale = 0.0
        elif ai_state != 3 and self._is_stunned:
            self._is_stunned = False
            mesh.GlobalAnimRateScale = 1.0
    
    def get_state_dict(self):
        """获取当前状态（主机上报用）"""
        loc = self.GetActorLocation()
        rot = self.GetActorRotation()
        ai_state_val = 0
        if self.ai:
            state_map = {
                EnemyState.IDLE: 0,
                EnemyState.CHASE: 1,
                EnemyState.ATTACK: 2,
                EnemyState.STUNNED: 3,
                EnemyState.DEAD: 4,
            }
            ai_state_val = state_map.get(self.ai.state, 0)
        
        is_attacking = False
        if self.ai and self.ai.state == EnemyState.ATTACK and self._attack_cooldown_active():
            is_attacking = True
        
        return {
            "enemy_id": self.enemy_id,
            "enemy_type": 0 if self.__class__.__name__ == "MeleeEnemy" else 1,
            "location": {"x": loc.x, "y": loc.y, "z": loc.z},
            "hp": int(self.health.current_hp) if self.health and not self.health.is_dead() else 0,
            "ai_state": ai_state_val,
            "is_attacking": is_attacking,
            "rotation": {"pitch": rot.pitch, "yaw": rot.yaw, "roll": rot.roll},
        }
    
    def _attack_cooldown_active(self):
        """检查攻击冷却是否正在进行（判断是否正在攻击）"""
        if self.ai and self.ai._attack_cooldown_timer > 0:
            return True
        return False
