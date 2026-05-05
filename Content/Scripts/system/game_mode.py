# -*- encoding: utf-8 -*-
"""关卡游戏模式 — 管理敌人数、关卡切换"""

import ue
import time

# 模块级单例，供其他模块访问 GameMode 实例
# （NePy World 不暴露 GetAuthGameMode）
_instance = None


@ue.uclass()
class TPSGameMode(ue.GameModeBase):
    """TPS 游戏模式

    职责：
    - 统计本关敌人数
    - 敌人死亡时递减，为0触发胜利
    - 玩家死亡触发失败
    - 管理关卡切换（OpenLevel）
    """

    def __init_pyobj__(self):
        self.alive_enemies = 0
        self.current_level = 0
        self._level_complete = False
        self._is_main_menu = False
        self._pending_show_menu = False
        self._pending_restore_input = False
        self._game_result = None  # None/"victory"/"defeat"
        self._pending_result_widget = None  # None/True(victory)/False(defeat)

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        global _instance
        _instance = self

        ts = time.strftime("%H:%M:%S")
        level_name = self.GetWorld().GetOuter().GetName()
        ue.LogWarning(f"[{ts}] TPSGameMode: raw level_name='{level_name}'")

        if "MainMenu" in level_name:
            self._is_main_menu = True
            self._pending_show_menu = True
            ue.LogWarning(f"[{ts}] TPSGameMode: MainMenu detected")
            return

        # 游戏关卡
        self._is_main_menu = False
        self._game_result = None
        self._level_complete = False
        self._count_enemies()

        if "Level1" in level_name:
            self.current_level = 1
        elif "Level2" in level_name:
            self.current_level = 2
        else:
            self.current_level = 1

        ue.LogWarning(f"[{ts}] TPSGameMode: Level {self.current_level} started, enemies={self.alive_enemies}")
        self._pending_restore_input = True

    def _count_enemies(self):
        """统计场景中所有敌人"""
        from enemy.base_enemy import BaseEnemy
        actors = ue.GameplayStatics.GetAllActorsOfClass(self, BaseEnemy)
        self.alive_enemies = len(actors) if actors else 0

    def on_enemy_killed(self):
        """敌人死亡时调用"""
        self.alive_enemies -= 1
        ue.LogWarning(f"TPSGameMode: Enemy killed, remaining={self.alive_enemies}")

        if self.alive_enemies <= 0 and not self._level_complete:
            self._on_victory()

    def _show_result_widget(self, is_victory: bool):
        """在当前关卡上层显示结算 Widget"""
        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if not pc:
            ue.LogError("TPSGameMode: No PlayerController for result widget!")
            return

        widget_class = ue.LoadObject(ue.Class, "/Game/BluePrint/WBP_GameResult.WBP_GameResult_C")
        if not widget_class:
            ue.LogError("TPSGameMode: Failed to load WBP_GameResult_C!")
            return

        widget = ue.WidgetBlueprintLibrary.Create(self, widget_class, pc)
        if widget:
            widget.ResultType = "胜利" if is_victory else "失败"
            widget.bIsFocusable = True
            widget.AddToViewport(0)
            pc.bShowMouseCursor = True
            widget.SetKeyboardFocus()
            result = "胜利" if is_victory else "失败"
            ue.LogWarning(f"TPSGameMode: Result widget shown ({result})")
        else:
            ue.LogError("TPSGameMode: CreateWidget returned None!")

    def _on_victory(self):
        """胜利 — Level1进下一关，Level2延迟一帧显示结算界面"""
        self._level_complete = True
        self._game_result = "victory"
        ue.LogWarning(f"TPSGameMode: Level {self.current_level} VICTORY!")

        if self.current_level == 1:
            self.next_level()
        else:
            # 延迟到下一帧玩家tick中创建Widget，与死亡逻辑一致
            self._pending_result_widget = True

    def on_player_died(self):
        """玩家死亡时调用"""
        if self._game_result:
            return
        self._game_result = "defeat"
        self._level_complete = True
        ue.LogWarning("TPSGameMode: Player DEFEATED!")
        # 延迟到下一帧玩家tick中创建Widget
        self._pending_result_widget = False

    def retry_level(self):
        """重新挑战当前关卡"""
        level_names = {1: "Level1", 2: "Level2"}
        name = level_names.get(self.current_level, "Level1")
        ue.GameplayStatics.OpenLevel(self, name)

    def back_to_menu(self):
        """返回主菜单"""
        ue.GameplayStatics.OpenLevel(self, "MainMenu")

    def next_level(self):
        """进入下一关（仅Level1胜利时）"""
        if self.current_level == 1:
            ue.GameplayStatics.OpenLevel(self, "Level2")

    def _show_main_menu(self):
        """主菜单 Widget 创建由蓝图处理"""
        ue.LogWarning("TPSGameMode: Main menu flag set")

    def _restore_game_input(self):
        """恢复游戏输入模式"""
        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if pc:
            pc.bShowMouseCursor = False
            ue.LogWarning("TPSGameMode: Game input restore attempted")

    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        if self._pending_show_menu:
            pc = ue.GameplayStatics.GetPlayerController(self, 0)
            if pc:
                self._pending_show_menu = False
                self._show_main_menu()

        if self._pending_restore_input:
            self._pending_restore_input = False
            self._restore_game_input()
