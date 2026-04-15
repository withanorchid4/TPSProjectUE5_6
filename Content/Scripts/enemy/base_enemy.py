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
    DEATH_DESTROY_DELAY = 2.0
    
    def __init_pyobj__(self):
        self.health = None
        self.ai = None
        self._death_timer = 0.0
        self._pending_hit_reset = False
        self._is_stunned = False
        self._target_yaw = None       # 目标朝向（平滑旋转用）
        self._rotation_speed = 15.0    # 旋转插值速度
    
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
        self.SetActorEnableCollision(False)
        self._death_timer = self.DEATH_DESTROY_DELAY
        ue.Log(f"BaseEnemy: {self} died")
    
    def _on_damage(self, amount: float, attacker=None):
        """受伤回调 — 推送 bIsHit 脉冲"""
        mesh = self.GetMesh()
        if mesh:
            anim = mesh.GetAnimInstance()
            if anim:
                anim.bIsHit = True
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
        # 更新AI
        if self.ai and not self.health.is_dead():
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
        
        # 死亡延迟销毁
        if self.health and self.health.is_dead():
            self._death_timer -= delta_time
            if self._death_timer <= 0.0:
                self.Destroy()
    
    @ue.ufunction(override=True)
    def ReceiveEndPlay(self, end_play_reason):
        ue.Log(f"{self} ReceiveEndPlay")
