# -*- encoding: utf-8 -*-
"""血量组件 - 敌人/玩家共用"""


class HealthComponent:
    """
    血量管理组件
    
    Usage:
        health = HealthComponent(owner, max_hp=100.0)
        health.on_death = lambda: owner.handle_death()
        health.on_damage = lambda amount, attacker: owner.handle_damage(amount, attacker)
    """
    
    def __init__(self, owner, max_hp=100.0):
        self.owner = owner
        self.max_hp = max_hp
        self.current_hp = max_hp
        
        # 回调
        self.on_death = None
        self.on_damage = None
    
    def take_damage(self, amount: float, attacker=None) -> float:
        """
        受到伤害
        
        Args:
            amount: 伤害值
            attacker: 攻击者（可选）
        
        Returns:
            实际造成的伤害
        """
        if self.current_hp <= 0:
            return 0.0
        
        actual = min(amount, self.current_hp)
        self.current_hp -= actual
        self.current_hp = max(0.0, self.current_hp)
        
        if self.on_damage:
            self.on_damage(actual, attacker)
        
        if self.current_hp <= 0 and self.on_death:
            self.on_death()
        
        return actual
    
    def heal(self, amount: float) -> float:
        """
        回血
        
        Args:
            amount: 回血量
        
        Returns:
            实际回血量
        """
        if self.current_hp <= 0:
            return 0.0
        old = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        return self.current_hp - old
    
    def is_dead(self) -> bool:
        """是否死亡"""
        return self.current_hp <= 0
    
    def get_hp_ratio(self) -> float:
        """获取血量比例 0~1"""
        if self.max_hp <= 0:
            return 0.0
        return self.current_hp / self.max_hp
