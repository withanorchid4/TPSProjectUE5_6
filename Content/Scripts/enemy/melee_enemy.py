# -*- encoding: utf-8 -*-
"""近战敌人"""

import ue
from .base_enemy import BaseEnemy
from system.enemy_ai_component import EnemyAIComponent


@ue.uclass()
class MeleeEnemy(BaseEnemy):
    """
    近战敌人 — 追到身边攻击玩家
    
    参数: detect_range=800, attack_range=150, move_speed=300
    """
    
    DEFAULT_MAX_HP = 80.0
    MELEE_DAMAGE = 15.0
    HIT_DELAY = 0.5  # 出拳帧延迟（秒）
    
    ATTACK_MONTAGE_PATH = "/Game/Variant_Combat/Anims/AM_ComboAttack.AM_ComboAttack"
    
    def __init_pyobj__(self):
        super().__init_pyobj__()
        self._hit_timer = -1.0
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        super().ReceiveTick(delta_time)
        # 延迟扣血：等动画播到出拳帧
        if self._hit_timer > 0:
            self._hit_timer -= delta_time
            if self._hit_timer <= 0:
                self._hit_timer = -1.0
                self._deal_melee_damage()
    
    def _setup_weapon(self):
        """近战敌人不持枪，使用空手动画"""
        mesh = self.GetMesh()
        if not mesh:
            return
        anim = mesh.GetAnimInstance()
        if anim:
            anim.bHasWeapon = False
    
    def _create_ai_component(self) -> EnemyAIComponent:
        return EnemyAIComponent(
            self,
            detect_range=800.0,
            attack_range=150.0,
            lose_range=1500.0,
            attack_cooldown=1.5,
            move_speed=300.0
        )
    
    def attack(self):
        """近战攻击：播放攻击蒙太奇，延迟到出拳帧扣血"""
        mesh = self.GetMesh()
        if mesh:
            anim = mesh.GetAnimInstance()
            if anim:
                attack_montage = ue.LoadObject(ue.AnimMontage, self.ATTACK_MONTAGE_PATH)
                if attack_montage:
                    anim.Montage_Play(attack_montage, 1.0)
        
        # 启动延迟扣血计时器
        self._hit_timer = self.HIT_DELAY
    
    def _deal_melee_damage(self):
        """出拳帧时对范围内玩家造成伤害"""
        player = self.ai._find_player()
        if not player:
            return
        
        dist = self.GetDistanceTo(player)
        if dist > self.ai.attack_range * 1.4:
            return
        
        if hasattr(player, 'take_damage'):
            player.take_damage(self.MELEE_DAMAGE, self)
            ue.Log(f"MeleeEnemy: Hit player for {self.MELEE_DAMAGE} damage")
            if hasattr(player, 'audio') and player.audio:
                player.audio.play_enemy_attack(self.GetActorLocation())
