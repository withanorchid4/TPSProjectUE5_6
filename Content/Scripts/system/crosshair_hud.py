# -*- encoding: utf-8 -*-
"""准星 HUD — 在屏幕中心绘制十字准星"""

import ue


@ue.uclass()
class CrosshairHUD(ue.HUD):
    """
    十字准星 HUD
    
    在屏幕中心用 DrawLine 画4条短线形成十字
    持枪时显示，收枪时隐藏
    """

    # 准星参数
    CROSSHAIR_SIZE = 10.0       # 线段长度
    CROSSHAIR_GAP = 4.0        # 中心空隙
    CROSSHAIR_THICKNESS = 2.0  # 线段粗细
    CROSSHAIR_COLOR = (0.0, 1.0, 0.0, 1.0)  # 绿色 RGBA

    def __init_pyobj__(self):
        self._cached_player = None

    @ue.ufunction(override=True)
    def ReceiveDrawHUD(self, size_x, size_y):
        """每帧绘制 HUD"""
        # 检查玩家是否持枪
        player = self._get_player()
        if not player:
            return

        if not getattr(player, '_is_weapon_drawn', False):
            return

        # 屏幕中心
        center_x = size_x / 2.0
        center_y = size_y / 2.0

        color = ue.LinearColor(*self.CROSSHAIR_COLOR)
        size = self.CROSSHAIR_SIZE
        gap = self.CROSSHAIR_GAP
        thick = self.CROSSHAIR_THICKNESS

        # 上
        self.DrawLine(center_x, center_y - gap, center_x, center_y - gap - size, color, thick)
        # 下
        self.DrawLine(center_x, center_y + gap, center_x, center_y + gap + size, color, thick)
        # 左
        self.DrawLine(center_x - gap, center_y, center_x - gap - size, center_y, color, thick)
        # 右
        self.DrawLine(center_x + gap, center_y, center_x + gap + size, center_y, color, thick)

    def _get_player(self):
        """获取玩家角色（带缓存）"""
        if self._cached_player:
            return self._cached_player

        pawn = self.GetOwningPawn()
        if pawn and hasattr(pawn, '_is_weapon_drawn'):
            self._cached_player = pawn
            return pawn
        return None
