# -*- encoding: utf-8 -*-
"""主菜单界面控制器

控制 WBP_MainMenu：显示角色列表、创建角色、开始游戏。

WBP_MainMenu 需要的命名控件：
- btn_char_0 / btn_char_1 / btn_char_2 / btn_char_3 — Button，4个角色槽位
- txt_char_0 / txt_char_1 / txt_char_2 / txt_char_3 — TextBlock，对应槽位文本
- etb_new_name     — EditableTextBox，输入新角色名
- btn_create_char  — Button，创建角色
- btn_delete_char  — Button，删除选中角色
- btn_start_game   — Button，开始游戏
- txt_status       — TextBlock，状态信息
"""

import ue

MAX_CHAR_SLOTS = 4


class MainMenuPanel:
    """主菜单面板控制器"""

    WBP_PATH = "/Game/BluePrint/WBP_MainMenu.WBP_MainMenu_C"

    def __init__(self, parent, pc, chars=None):
        self._parent = parent
        self._pc = pc
        self._widget = None
        self._nm = None
        self._destroyed = False
        self._chars = chars or []
        self._selected_char_id = None

        # 创建 Widget
        widget_class = ue.LoadObject(ue.Class, self.WBP_PATH)
        if not widget_class:
            ue.LogError("MainMenuPanel: Failed to load WBP_MainMenu_C!")
            return

        self._widget = ue.WidgetBlueprintLibrary.Create(parent, widget_class, pc)
        if not self._widget:
            ue.LogError("MainMenuPanel: CreateWidget returned None!")
            return

        # 绑定固定按钮事件
        try:
            self._widget.btn_start_game.OnClicked.Add(self._on_start_game)
            self._widget.btn_create_char.OnClicked.Add(self._on_create_char)
            self._widget.btn_delete_char.OnClicked.Add(self._on_delete_char)
        except Exception as e:
            ue.LogWarning(f"MainMenuPanel: Delegate binding failed ({e})")

        # 绑定画质设置按钮
        try:
            self._widget.btn_graphics_settings.OnClicked.Add(self._on_graphics_settings)
        except Exception as e:
            ue.LogWarning(f"MainMenuPanel: btn_graphics_settings binding failed ({e})")

        # 绑定角色槽位按钮
        for i in range(MAX_CHAR_SLOTS):
            btn = self._find_widget(f"btn_char_{i}")
            if btn:
                try:
                    btn.OnClicked.Add(lambda _i=i: self._on_char_slot_clicked(_i))
                except Exception:
                    pass

        # 填充角色列表
        self._refresh_slots()

        # 显示到视口
        self._widget.bIsFocusable = True
        self._widget.AddToViewport(0)
        pc.bShowMouseCursor = True
        self._widget.SetKeyboardFocus()

        # 获取 NetworkManager
        from network.network_manager import NetworkManager
        self._nm = NetworkManager.get_instance()

        # 注册回调
        if self._nm:
            self._nm.on_character_list = self._on_character_list
            self._nm.on_create_result = self._on_create_result
            self._nm.on_delete_result = self._on_delete_result
            self._nm.on_enter_game = self._on_enter_game

        ue.LogWarning("MainMenuPanel: Shown")

    # ─── 角色槽位 ───

    def _refresh_slots(self):
        """根据 _chars 刷新4个槽位的显示"""
        if not self._widget:
            return

        for i in range(MAX_CHAR_SLOTS):
            txt = self._find_widget(f"txt_char_{i}")
            btn = self._find_widget(f"btn_char_{i}")

            if i < len(self._chars):
                c = self._chars[i]
                # 有角色：显示名称+等级，按钮可见
                if txt:
                    try:
                        label = f"{c['char_name']}  Lv.{c['level']}"
                        if c["char_id"] == self._selected_char_id:
                            label = f"[ {label} ]"
                        txt.SetText(label)
                    except Exception:
                        pass
                if btn:
                    try:
                        btn.SetVisibility(ue.ESlateVisibility.Visible)
                    except Exception:
                        pass
            else:
                # 空槽位：显示空白，按钮隐藏或不可交互
                if txt:
                    try:
                        txt.SetText("")
                    except Exception:
                        pass
                if btn:
                    try:
                        btn.SetVisibility(ue.ESlateVisibility.Hidden)
                    except Exception:
                        pass

    def _on_char_slot_clicked(self, index):
        """点击角色槽位"""
        if self._destroyed or index >= len(self._chars):
            return
        c = self._chars[index]
        self._selected_char_id = c["char_id"]
        ue.LogWarning(f"MainMenuPanel: Selected char '{c['char_name']}' (id={c['char_id']})")
        self._refresh_slots()

    # ─── 按钮回调 ───

    def _on_start_game(self):
        if self._destroyed or not self._nm:
            return
        if self._selected_char_id:
            self._set_status("Entering game...")
            self._nm.select_character(self._selected_char_id)
        else:
            self._set_status("No character! Please select or create one.")

    def _on_create_char(self):
        if self._destroyed or not self._nm:
            return
        if len(self._chars) >= MAX_CHAR_SLOTS:
            self._set_status("Max characters reached!")
            return
        name = self._get_text("etb_new_name")
        if not name:
            self._set_status("Please enter a character name")
            return
        self._set_status("Creating character...")
        self._nm.create_character(name)

    def _on_delete_char(self):
        """删除选中角色"""
        if self._destroyed or not self._nm:
            return
        if not self._selected_char_id:
            self._set_status("Please select a character first")
            return
        self._set_status("Deleting character...")
        self._nm.delete_character(self._selected_char_id)

    def _on_graphics_settings(self):
        """画质设置按钮回调"""
        if self._destroyed:
            return
        if self._on_graphics_settings_callback:
            try:
                self._on_graphics_settings_callback()
            except Exception as e:
                ue.LogError(f"MainMenuPanel: graphics_settings callback error: {e}")

    # ─── NetworkManager 回调 ───

    def _on_character_list(self, chars):
        if self._destroyed:
            return
        ue.LogWarning(f"MainMenuPanel: _on_character_list called with {len(chars)} chars")
        self._chars = chars
        # 如果当前选中不在新列表中，重新选中
        valid_ids = [c["char_id"] for c in self._chars]
        if self._selected_char_id not in valid_ids:
            self._selected_char_id = self._chars[0]["char_id"] if self._chars else None
        self._refresh_slots()
        self._set_status("")

    def _on_create_result(self, success, char_info):
        if self._destroyed:
            return
        if success and char_info:
            self._selected_char_id = char_info["char_id"]
            self._set_status(f"Character '{char_info['char_name']}' created!")
            if self._nm:
                ue.LogWarning("MainMenuPanel: Refreshing character list after creation...")
                self._nm.get_characters()
        else:
            self._set_status("Create character failed")

    def _on_delete_result(self, success, msg, char_id):
        if self._destroyed:
            return
        if success:
            self._selected_char_id = None
            self._set_status("Character deleted!")
            if self._nm:
                ue.LogWarning("MainMenuPanel: Refreshing character list after deletion...")
                self._nm.get_characters()
        else:
            self._set_status(f"Delete failed: {msg}")

    def _on_enter_game(self, player_id):
        if self._destroyed:
            return
        ue.LogWarning(f"MainMenuPanel: Entered game! player_id={player_id}")
        if self._on_enter_game_callback:
            try:
                self._on_enter_game_callback()
            except Exception as e:
                ue.LogError(f"MainMenuPanel: on_enter_game_callback error: {e}")
        self.destroy()

    # ─── 公开接口 ───

    def set_enter_game_callback(self, callback):
        self._on_enter_game_callback = callback

    def set_graphics_settings_callback(self, callback):
        """设置画质设置按钮回调"""
        self._on_graphics_settings_callback = callback

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        if self._nm:
            self._nm.on_character_list = None
            self._nm.on_create_result = None
            self._nm.on_delete_result = None
        if self._widget:
            try:
                self._widget.RemoveFromParent()
            except Exception:
                pass
            self._widget = None
        ue.LogWarning("MainMenuPanel: Destroyed")

    # ─── 内部工具 ───

    def _get_text(self, widget_name):
        try:
            w = self._find_widget(widget_name)
            if w:
                text = w.GetText()
                return str(text).strip() if text else ""
        except Exception as e:
            ue.LogWarning(f"MainMenuPanel: _get_text({widget_name}) error: {e}")
        return ""

    def _clear_status(self, delta=0):
        if self._destroyed:
            return False
        try:
            w = self._find_widget("txt_status")
            if w:
                w.SetText("")
        except Exception:
            pass
        return False

    def _set_status(self, msg):
        try:
            w = self._find_widget("txt_status")
            if w:
                w.SetText(msg)
        except Exception:
            pass
        if msg:
            ue.LogWarning(f"MainMenuPanel: [STATUS] {msg}")
        ue.AddTicker(self._clear_status, 5.0)

    def _find_widget(self, name):
        if not self._widget:
            return None
        try:
            w = getattr(self._widget, name, None)
            if w:
                return w
        except Exception:
            pass
        try:
            w = self._widget.GetWidgetFromName(name)
            if w:
                return w
        except Exception:
            pass
        return None

    _on_enter_game_callback = None
    _on_graphics_settings_callback = None
