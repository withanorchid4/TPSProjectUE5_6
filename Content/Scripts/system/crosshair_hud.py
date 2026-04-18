# -*- encoding: utf-8 -*-
"""游戏 HUD — 准星 + 血条 + 弹药 + 伤害跳字"""

import ue


@ue.uclass()
class CrosshairHUD(ue.HUD):
    """
    游戏 HUD
    
    功能:
    - 十字准星（持枪时显示）
    - 玩家血条（左下角）
    - 弹药显示（右下角）
    - 伤害跳字（敌头顶浮动）
    """

    # ── 准星参数 ──
    CROSSHAIR_SIZE = 10.0
    CROSSHAIR_GAP = 4.0
    CROSSHAIR_THICKNESS = 2.0
    CROSSHAIR_COLOR = (0.0, 1.0, 0.0, 1.0)

    # ── 血条参数 ──
    HP_BAR_WIDTH = 250.0
    HP_BAR_HEIGHT = 25.0
    HP_BAR_MARGIN_X = 40.0
    HP_BAR_MARGIN_Y = 70.0
    HP_BAR_BG_COLOR = (0.1, 0.1, 0.1, 0.7)
    HP_BAR_FG_COLOR = (0.0, 0.8, 0.2, 0.9)
    HP_BAR_LOW_COLOR = (0.9, 0.15, 0.1, 0.9)
    HP_LOW_THRESHOLD = 0.3

    # ── 弹药参数 ──
    AMMO_MARGIN_X = 40.0
    AMMO_MARGIN_Y = 70.0

    # ── 伤害跳字参数 ──
    DAMAGE_DURATION = 1.0
    DAMAGE_FLOAT_SPEED = 80.0

    def __init_pyobj__(self):
        self._cached_player = None
        self._damage_numbers = []  # [{pos, amount, time}]

    @ue.ufunction(override=True)
    def ReceiveDrawHUD(self, size_x, size_y):
        player = self._get_player()
        if not player:
            return

        # 1) 准星
        if getattr(player, '_is_weapon_drawn', False):
            self._draw_crosshair(size_x, size_y)

        # 2) 血条
        if hasattr(player, 'health') and player.health:
            self._draw_health_bar(size_x, size_y, player)

        # 3) Buff状态
        if hasattr(player, 'buff_component') and player.buff_component:
            self._draw_buffs(size_x, size_y, player)

        # 4) 弹药
        if hasattr(player, 'shooting') and player.shooting:
            self._draw_ammo(size_x, size_y, player)

        # 5) 伤害跳字
        self._draw_damage_numbers(size_x, size_y)

    # ────────────────────────────────────────
    # 准星
    # ────────────────────────────────────────
    def _draw_crosshair(self, size_x, size_y):
        center_x = size_x / 2.0
        center_y = size_y / 2.0
        color = ue.LinearColor(*self.CROSSHAIR_COLOR)
        s, g, t = self.CROSSHAIR_SIZE, self.CROSSHAIR_GAP, self.CROSSHAIR_THICKNESS

        self.DrawLine(center_x, center_y - g, center_x, center_y - g - s, color, t)
        self.DrawLine(center_x, center_y + g, center_x, center_y + g + s, color, t)
        self.DrawLine(center_x - g, center_y, center_x - g - s, center_y, color, t)
        self.DrawLine(center_x + g, center_y, center_x + g + s, center_y, color, t)

    # ────────────────────────────────────────
    # 血条
    # ────────────────────────────────────────
    def _draw_health_bar(self, size_x, size_y, player):
        health = player.health
        hp_ratio = health.get_hp_ratio()
        bar_x = self.HP_BAR_MARGIN_X
        bar_y = size_y - self.HP_BAR_MARGIN_Y

        # 背景
        bg_color = ue.LinearColor(*self.HP_BAR_BG_COLOR)
        self.DrawRect(bg_color, bar_x, bar_y, self.HP_BAR_WIDTH, self.HP_BAR_HEIGHT)

        # 前景
        if hp_ratio > self.HP_LOW_THRESHOLD:
            fg_color = ue.LinearColor(*self.HP_BAR_FG_COLOR)
        else:
            fg_color = ue.LinearColor(*self.HP_BAR_LOW_COLOR)
        fg_width = self.HP_BAR_WIDTH * hp_ratio
        if fg_width > 0:
            self.DrawRect(fg_color, bar_x, bar_y, fg_width, self.HP_BAR_HEIGHT)

        # 文字
        hp_text = f"HP {health.current_hp:.0f}/{health.max_hp:.0f}"
        text_color = ue.LinearColor(1.0, 1.0, 1.0, 1.0)
        self.DrawText(hp_text, text_color, bar_x + 8.0, bar_y + 4.0, None, 1.0, False)

    # ────────────────────────────────────────
    # 弹药
    # ────────────────────────────────────────
    def _draw_ammo(self, size_x, size_y, player):
        shooting = player.shooting
        text_x = size_x - self.AMMO_MARGIN_X
        text_y = size_y - self.AMMO_MARGIN_Y

        # 弹药数
        ammo_text = f"{shooting.current_ammo} / {shooting.total_ammo}"
        color = ue.LinearColor(1.0, 1.0, 1.0, 1.0)
        self.DrawText(ammo_text, color, text_x - 120.0, text_y, None, 1.0, False)

        # 射击模式
        mode = "AUTO" if shooting.is_auto_mode() else "SEMI"
        mode_color = ue.LinearColor(0.5, 0.8, 1.0, 0.8)
        self.DrawText(mode, mode_color, text_x - 120.0, text_y - 25.0, None, 0.8, False)

        # 换弹提示
        if shooting.is_reloading():
            reload_color = ue.LinearColor(1.0, 0.8, 0.0, 0.9)
            self.DrawText("RELOADING...", reload_color, text_x - 200.0, text_y - 55.0, None, 0.9, False)

    # ────────────────────────────────────────
    # Buff状态
    # ────────────────────────────────────────
    def _draw_buffs(self, size_x, size_y, player):
        buff_comp = player.buff_component
        # 按类型聚合
        buff_types = {}
        for buff in buff_comp.get_all_buffs():
            if buff.buff_type not in buff_types:
                buff_types[buff.buff_type] = {"stacks": 0, "remaining": 0.0}
            buff_types[buff.buff_type]["stacks"] += 1
            if buff.remaining > buff_types[buff.buff_type]["remaining"]:
                buff_types[buff.buff_type]["remaining"] = buff.remaining

        if not buff_types:
            return

        bar_x = self.HP_BAR_MARGIN_X
        bar_y = size_y - self.HP_BAR_MARGIN_Y - self.HP_BAR_HEIGHT - 8.0

        for buff_type, info in buff_types.items():
            if buff_type == "attack_up":
                label = f"ATK\u2191 x{info['stacks']} [{info['remaining']:.0f}s]"
                color = ue.LinearColor(0.2, 1.0, 0.3, 0.9)
            elif buff_type == "attack_down":
                label = f"ATK\u2193 x{info['stacks']} [{info['remaining']:.0f}s]"
                color = ue.LinearColor(1.0, 0.3, 0.2, 0.9)
            else:
                label = f"{buff_type} x{info['stacks']} [{info['remaining']:.0f}s]"
                color = ue.LinearColor(1.0, 1.0, 1.0, 0.7)

            self.DrawText(label, color, bar_x, bar_y, None, 0.9, False)
            bar_y -= 22.0

    # ────────────────────────────────────────
    # 伤害跳字
    # ────────────────────────────────────────
    def add_damage_number(self, world_pos, amount):
        """添加伤害数字（由其他类调用）"""
        self._damage_numbers.append({
            'pos': world_pos,
            'amount': amount,
            'time': 0.0,
        })

    def _draw_damage_numbers(self, size_x, size_y):
        """绘制并更新伤害跳字"""
        game_time = self.GetGameTimeSinceCreation()
        remaining = []

        for entry in self._damage_numbers:
            if entry['time'] == 0.0:
                entry['time'] = game_time

            elapsed = game_time - entry['time']
            if elapsed > self.DAMAGE_DURATION:
                continue

            # 世界坐标 → 屏幕坐标
            screen_pos = self.Project(entry['pos'])
            if not screen_pos:
                remaining.append(entry)
                continue

            # 上浮
            sx = screen_pos.X
            sy = screen_pos.Y - elapsed * self.DAMAGE_FLOAT_SPEED

            # 淡出
            alpha = 1.0 - (elapsed / self.DAMAGE_DURATION)
            color = ue.LinearColor(1.0, 0.9, 0.0, alpha)

            text = f"-{entry['amount']:.0f}"
            self.DrawText(text, color, sx, sy, None, 1.2, False)

            remaining.append(entry)

        self._damage_numbers = remaining

    # ────────────────────────────────────────
    # 工具
    # ────────────────────────────────────────
    def _get_player(self):
        if self._cached_player:
            return self._cached_player
        pawn = self.GetOwningPawn()
        if pawn and hasattr(pawn, '_is_weapon_drawn'):
            self._cached_player = pawn
            return pawn
        return None