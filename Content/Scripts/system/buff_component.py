# -*- encoding: utf-8 -*-
"""Buff管理组件 — 纯管理逻辑，不包含任何触发条件

触发逻辑由外部调用者决定（按键、受伤、道具等），
本组件只负责：添加/移除/计时/查询。
"""


class BuffData:
    """单个Buff实例"""

    __slots__ = ('buff_type', 'multiplier', 'remaining')

    def __init__(self, buff_type: str, multiplier: float, duration: float):
        self.buff_type = buff_type
        self.multiplier = multiplier
        self.remaining = duration


class BuffComponent:
    """Buff管理组件

    用法:
        buff_comp = BuffComponent(owner)
        buff_comp.add_buff("attack_up")    # 外部触发
        buff_comp.add_buff("attack_down")  # 外部触发
        buff_comp.tick(delta_time)          # 每帧调用
        multiplier = buff_comp.get_attack_multiplier()
    """

    # ── 全局上限 ──
    MAX_STACKS = 3           # 所有类型合计最多3层
    ADD_INTERVAL = 2.0       # 同类Buff添加间隔（秒）

    # ── Buff配置表（可扩展） ──
    BUFF_CONFIGS = {
        "attack_up":   {"multiplier": 0.3,  "duration": 10.0},
        "attack_down": {"multiplier": -0.2, "duration": 8.0},
    }

    def __init__(self, owner):
        self.owner = owner
        self.buffs: list = []               # 活跃Buff列表
        self._last_add_time: dict = {}      # {buff_type: 上次添加时间}

    def add_buff(self, buff_type: str) -> bool:
        """添加一个Buff（由外部触发调用）

        Args:
            buff_type: Buff类型名，必须在BUFF_CONFIGS中

        Returns:
            是否成功添加
        """
        config = self.BUFF_CONFIGS.get(buff_type)
        if not config:
            return False

        # 间隔CD检查
        current_time = self.owner.GetGameTimeSinceCreation()
        last_time = self._last_add_time.get(buff_type, -999.0)
        if current_time - last_time < self.ADD_INTERVAL:
            return False

        # 全局3层上限：满了则移除最早的
        if len(self.buffs) >= self.MAX_STACKS:
            self.buffs.pop(0)

        # 创建并添加
        buff = BuffData(
            buff_type=buff_type,
            multiplier=config["multiplier"],
            duration=config["duration"],
        )
        self.buffs.append(buff)
        self._last_add_time[buff_type] = current_time
        return True

    def tick(self, delta_time: float):
        """每帧更新（倒计时+过期移除）"""
        alive = []
        for buff in self.buffs:
            buff.remaining -= delta_time
            if buff.remaining > 0.0:
                alive.append(buff)
        self.buffs = alive

    def get_attack_multiplier(self) -> float:
        """计算最终攻击倍率"""
        result = 1.0
        for buff in self.buffs:
            result += buff.multiplier
        return max(0.1, result)

    def get_buff_stacks(self, buff_type: str) -> int:
        """查询指定类型的层数"""
        return sum(1 for b in self.buffs if b.buff_type == buff_type)

    def get_buff_remaining(self, buff_type: str) -> float:
        """查询指定类型最长剩余时间"""
        remaining = 0.0
        for b in self.buffs:
            if b.buff_type == buff_type and b.remaining > remaining:
                remaining = b.remaining
        return remaining

    def get_all_buffs(self) -> list:
        """获取所有活跃Buff（供HUD等外部查询）"""
        return list(self.buffs)

    def clear_all(self):
        """清除所有Buff"""
        self.buffs.clear()
        self._last_add_time.clear()
