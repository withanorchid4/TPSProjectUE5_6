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
        self._game_result = None  # None/"victory"/"defeat"
        self._pending_result_widget = None  # None/True(victory)/False(defeat)
        self._login_panel = None  # 登录界面控制器
        self._main_menu_panel = None  # 主菜单界面控制器
        self._graphics_settings_panel = None  # 画质设置面板控制器
        self._cached_chars = []  # 缓存角色列表（用于画质设置返回时重建主菜单）

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        global _instance
        _instance = self

        t0 = time.time()
        ts = time.strftime("%H:%M:%S")
        level_name = self.GetWorld().GetOuter().GetName()
        ue.LogWarning(f"[{ts}] TPSGameMode: raw level_name='{level_name}'")

        if "MainMenu" in level_name:
            self._is_main_menu = True
            # 用 AddTicker 延迟一帧显示菜单（ReceiveTick 在 NePy 中不可靠）
            self._menu_ticker = ue.AddTicker(self._deferred_show_menu, 1)
            ue.LogWarning(f"[{ts}] TPSGameMode: MainMenu detected, menu ticker added")
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

        elapsed = time.time() - t0
        ue.LogWarning(f"[{ts}] TPSGameMode: Level {self.current_level} started, enemies={self.alive_enemies}, Python init took {elapsed:.3f}s")
        # 用 AddTicker 延迟恢复输入（ReceiveTick 在 NePy 中不可靠）
        ue.AddTicker(self._deferred_restore_input, 1)

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

    def _deferred_show_menu(self, delta_time):
        """延迟一帧显示菜单（由 AddTicker 调用，返回 False 停止）"""
        try:
            pc = ue.GameplayStatics.GetPlayerController(self, 0)
            if pc:
                self._show_login_ui()
                return False  # 停止 ticker
            else:
                ue.LogWarning("TPSGameMode: No PC yet, retrying next frame...")
                return True  # 继续下一帧重试
        except Exception as e:
            ue.LogError(f"TPSGameMode: _deferred_show_menu error: {e}")
            return False  # 出错时停止 ticker，避免无限重试

    def _deferred_restore_input(self, delta_time):
        """延迟恢复输入模式"""
        self._restore_game_input()
        return False  # 停止 ticker

    def _show_login_ui(self):
        """显示登录界面"""
        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if not pc:
            ue.LogError("TPSGameMode: No PlayerController for login UI!")
            return

        from ui.login_ui import LoginPanel
        self._login_panel = LoginPanel(self, pc)
        self._login_panel.set_login_success_callback(self._on_login_success)
        ue.LogWarning("TPSGameMode: Login UI shown")

    def _on_login_success(self, chars):
        """登录成功回调：销毁登录界面，显示主菜单"""
        if self._login_panel:
            self._login_panel.destroy()
            self._login_panel = None

        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if not pc:
            ue.LogError("TPSGameMode: No PlayerController for main menu!")
            return

        from ui.main_menu_ui import MainMenuPanel
        self._main_menu_panel = MainMenuPanel(self, pc, chars)
        self._cached_chars = chars  # 缓存角色列表
        self._main_menu_panel.set_enter_game_callback(self._on_login_enter_game)
        self._main_menu_panel.set_graphics_settings_callback(self._on_show_graphics_settings)
        ue.LogWarning("TPSGameMode: Main menu shown")

    def _on_login_enter_game(self):
        """进入游戏：加载关卡"""
        ue.LogWarning("TPSGameMode: Login complete, loading Level1...")
        if self._main_menu_panel:
            self._main_menu_panel.destroy()
            self._main_menu_panel = None
        ue.GameplayStatics.OpenLevel(self, "Level1")

    def _restore_game_input(self):
        """恢复游戏输入模式"""
        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if pc:
            pc.bShowMouseCursor = False
            ue.LogWarning("TPSGameMode: Game input restore attempted")

    def _on_show_graphics_settings(self):
        """显示画质设置面板"""
        if self._main_menu_panel:
            self._main_menu_panel.destroy()
            self._main_menu_panel = None

        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if not pc:
            ue.LogError("TPSGameMode: No PlayerController for graphics settings!")
            return

        from ui.graphics_settings_ui import GraphicsSettingsPanel
        self._graphics_settings_panel = GraphicsSettingsPanel(self, pc)
        self._graphics_settings_panel.set_back_callback(self._on_graphics_settings_back)
        ue.LogWarning("TPSGameMode: Graphics settings panel shown")

    def _on_graphics_settings_back(self):
        """从画质设置返回主菜单"""
        if self._graphics_settings_panel:
            self._graphics_settings_panel.destroy()
            self._graphics_settings_panel = None

        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if not pc:
            return

        from ui.main_menu_ui import MainMenuPanel
        self._main_menu_panel = MainMenuPanel(self, pc, self._cached_chars)
        self._main_menu_panel.set_enter_game_callback(self._on_login_enter_game)
        self._main_menu_panel.set_graphics_settings_callback(self._on_show_graphics_settings)
        ue.LogWarning("TPSGameMode: Back to main menu")


