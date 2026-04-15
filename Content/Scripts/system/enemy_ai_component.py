# -*- encoding: utf-8 -*-
"""敌人AI组件 - Python状态机 + NavMesh寻路"""

import ue
from enum import Enum


class EnemyState(Enum):
    IDLE = "idle"
    CHASE = "chase"
    ATTACK = "attack"
    STUNNED = "stunned"
    DEAD = "dead"


class EnemyAIComponent:
    """
    敌人AI状态机组件
    
    状态: IDLE → CHASE → ATTACK → STUNNED → DEAD
    
    用法:
        ai = EnemyAIComponent(owner, detect_range=800, attack_range=150, ...)
        ai.on_chase = lambda: owner.move_to_player()
        ai.on_attack = lambda: owner.attack()
        ai.tick(delta_time)
    """
    
    def __init__(self, owner, detect_range=800.0, attack_range=150.0,
                 lose_range=1500.0, attack_cooldown=1.5, move_speed=300.0):
        self.owner = owner
        self.state = EnemyState.IDLE
        
        # 参数
        self.detect_range = detect_range
        self.attack_range = attack_range
        self.lose_range = lose_range
        self.attack_cooldown = attack_cooldown
        self.move_speed = move_speed
        
        # 计时器
        self._attack_cooldown_timer = 0.0
        self._stun_timer = 0.0
        
        # 回调
        self.on_chase = None
        self.on_attack = None
        self.on_stop = None
        self.on_stunned = None
        self.on_stun_end = None
        
        # 缓存
        self._player = None
    
    def _find_player(self):
        """查找玩家角色"""
        if self._player:
            return self._player
        all_actors = ue.GameplayStatics.GetAllActorsOfClass(
            self.owner.GetWorld(),
            ue.Character
        )
        for actor in all_actors:
            if hasattr(actor, 'movement') and hasattr(actor, 'shooting'):
                self._player = actor
                return actor
        return None
    
    def _get_distance_to_player(self) -> float:
        """获取到玩家的距离"""
        player = self._find_player()
        if not player:
            return 99999.0
        return self.owner.GetDistanceTo(player)
    
    def tick(self, delta_time: float):
        """每帧更新状态机"""
        if self.state == EnemyState.DEAD:
            return
        
        # 更新冷却
        if self._attack_cooldown_timer > 0:
            self._attack_cooldown_timer -= delta_time
        if self._stun_timer > 0:
            self._stun_timer -= delta_time
        
        # 状态机
        if self.state == EnemyState.IDLE:
            self._tick_idle()
        elif self.state == EnemyState.CHASE:
            self._tick_chase()
        elif self.state == EnemyState.ATTACK:
            self._tick_attack()
        elif self.state == EnemyState.STUNNED:
            self._tick_stunned()
    
    def _tick_idle(self):
        dist = self._get_distance_to_player()
        if dist < self.detect_range:
            self.state = EnemyState.CHASE
            ue.Log(f"EnemyAI: IDLE → CHASE (dist={dist:.0f})")
    
    def _tick_chase(self):
        dist = self._get_distance_to_player()
        
        if dist > self.lose_range:
            self.state = EnemyState.IDLE
            if self.on_stop:
                self.on_stop()
            ue.Log(f"EnemyAI: CHASE → IDLE (lost player)")
            return
        
        if dist < self.attack_range:
            self.state = EnemyState.ATTACK
            if self.on_stop:
                self.on_stop()
            ue.Log(f"EnemyAI: CHASE → ATTACK (in range)")
            return
        
        # 追击
        if self.on_chase:
            self.on_chase()
    
    def _tick_attack(self):
        dist = self._get_distance_to_player()
        
        if dist > self.attack_range * 1.2:
            self.state = EnemyState.CHASE
            ue.Log(f"EnemyAI: ATTACK → CHASE (out of range)")
            return
        
        if self._attack_cooldown_timer <= 0:
            if self.on_attack:
                self.on_attack()
            self._attack_cooldown_timer = self.attack_cooldown
    
    def _tick_stunned(self):
        if self._stun_timer <= 0:
            self.state = EnemyState.IDLE
            if self.on_stun_end:
                self.on_stun_end()
            ue.Log(f"EnemyAI: STUNNED → IDLE")
    
    def set_stunned(self, duration: float):
        """进入晕眩状态"""
        self.state = EnemyState.STUNNED
        self._stun_timer = duration
        if self.on_stop:
            self.on_stop()
        if self.on_stunned:
            self.on_stunned()
        ue.Log(f"EnemyAI: → STUNNED ({duration}s)")
    
    def set_dead(self):
        """进入死亡状态"""
        self.state = EnemyState.DEAD
        if self.on_stop:
            self.on_stop()
