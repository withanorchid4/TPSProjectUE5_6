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
    - 敌人死亡时递减，为0触发关卡完成
    - 管理关卡切换（OpenLevel）
    """

    LEVEL_COMPLETE_DELAY = 3.0  # 关卡完成后延迟秒数再切关

    def __init_pyobj__(self):
        self.alive_enemies = 0
        self.current_level = 0
        self._level_complete = False
        self._transition_timer = 0.0
        self._is_main_menu = False
        self._pending_show_menu = False
        self._pending_restore_input = False

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        global _instance
        _instance = self

        ts = time.strftime("%H:%M:%S")
        # 判断当前关卡
        level_name = self.GetWorld().GetOuter().GetName()
        ue.LogWarning(f"[{ts}] TPSGameMode: raw level_name='{level_name}'")
        if "MainMenu" in level_name:
            self._is_main_menu = True
            # Widget 创建延迟到 Tick，等 PlayerController 就绪
            self._pending_show_menu = True
            ue.LogWarning(f"[{ts}] TPSGameMode: MainMenu detected, will show widget")
            return

        # 游戏关卡：统计敌人
        self._is_main_menu = False
        self._count_enemies()

        if level_name == "Level1":
            self.current_level = 1
        elif level_name == "Level2":
            self.current_level = 2
        else:
            self.current_level = 1

        ue.LogWarning(f"[{ts}] TPSGameMode: Level {self.current_level} started, enemies={self.alive_enemies}")

        # 恢复游戏输入模式（从 MainMenu 的 UI Only 切换过来）
        self._pending_restore_input = True

    def _count_enemies(self):
        """统计场景中所有敌人"""
        from enemy.base_enemy import BaseEnemy
        actors = ue.GameplayStatics.GetAllActorsOfClass(self, BaseEnemy)
        if actors:
            self.alive_enemies = len(actors)
        else:
            self.alive_enemies = 0

    def on_enemy_killed(self):
        """敌人死亡时调用"""
        self.alive_enemies -= 1
        ue.LogWarning(f"TPSGameMode: Enemy killed, remaining={self.alive_enemies}")

        if self.alive_enemies <= 0 and not self._level_complete:
            self._on_level_complete()

    def _on_level_complete(self):
        """关卡完成"""
        self._level_complete = True
        ue.LogWarning(f"TPSGameMode: Level {self.current_level} complete!")
        # 直接切换，不用延迟（GameMode 的 ReceiveTick 在蓝图子类中不可靠）
        self._transition_to_next_level()

    def _show_main_menu(self):
        """主菜单 Widget 创建由蓝图处理，Python 只设标记"""
        ue.LogWarning("TPSGameMode: Main menu flag set, blueprint should create widget")

    def _restore_game_input(self):
        """恢复游戏输入模式"""
        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if pc:
            pc.bShowMouseCursor = False
            # 尝试用 UE 内置函数恢复输入模式
            try:
                input_mode = ue.FInputModeDataBase()
                game_mode = ue.FInputModeGameOnly()
                pc.SetInputMode(game_mode)
            except Exception as e:
                ue.LogWarning(f"TPSGameMode: SetInputMode failed: {e}, trying alternative")
                try:
                    pc.InputMode = 0  # Game Only = 0
                except Exception as e2:
                    ue.LogWarning(f"TPSGameMode: Alternative input mode failed: {e2}")
            ue.LogWarning("TPSGameMode: Game input restore attempted")

    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        # 主菜单：延迟创建 Widget
        if self._pending_show_menu:
            pc = ue.GameplayStatics.GetPlayerController(self, 0)
            if pc:
                self._pending_show_menu = False
                self._show_main_menu()

        # 游戏关卡：延迟恢复输入
        if self._pending_restore_input:
            self._pending_restore_input = False
            self._restore_game_input()

        if not self._level_complete:
            return

        self._transition_timer -= delta_time
        if self._transition_timer <= 0.0:
            self._transition_to_next_level()

    def _transition_to_next_level(self):
        """切换到下一关"""
        if self.current_level == 1:
            ue.GameplayStatics.OpenLevel(self, "Level2")
        elif self.current_level == 2:
            # 胜利，回到主菜单
            ue.GameplayStatics.OpenLevel(self, "MainMenu")
