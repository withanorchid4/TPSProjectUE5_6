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
        """近战攻击：对范围内玩家造成伤害"""
        player = self.ai._find_player()
        if not player:
            return
        
        dist = self.GetDistanceTo(player)
        if dist > self.ai.attack_range * 1.5:
            return
        
        # 对玩家造成伤害（需要玩家有 take_damage 方法）
        if hasattr(player, 'take_damage'):
            player.take_damage(self.MELEE_DAMAGE, self)
            ue.Log(f"MeleeEnemy: Hit player for {self.MELEE_DAMAGE} damage")
        else:
            ue.Log(f"MeleeEnemy: Attack! (player has no take_damage, dist={dist:.0f})")
