# -*- encoding: utf-8 -*-
"""登录界面控制器

使用 WidgetBlueprintLibrary.Create 创建 WBP_Login，绑定按钮事件，
通过 NetworkManager 逐步 API 完成登录/注册流程。

登录成功后获取角色列表，通知 game_mode 显示 WBP_MainMenu。
"""

import ue


class LoginPanel:
    """登录面板控制器

    职责：
    - 创建 WBP_Login Widget 并添加到视口
    - 绑定按钮点击事件
    - 处理登录/注册流程
    - 登录成功后获取角色列表，通知 game_mode 切到主菜单
    """

    # Widget 蓝图路径
    WBP_PATH = "/Game/BluePrint/WBP_Login.WBP_Login_C"

    def __init__(self, parent, pc):
        """
        Args:
            parent: UObject 上下文（GameMode）
            pc: PlayerController
        """
        self._parent = parent
        self._pc = pc
        self._widget = None
        self._nm = None
        self._destroyed = False

        # 创建 Widget
        widget_class = ue.LoadObject(ue.Class, self.WBP_PATH)
        if not widget_class:
            ue.LogError("LoginPanel: Failed to load WBP_Login_C!")
            return

        self._widget = ue.WidgetBlueprintLibrary.Create(parent, widget_class, pc)
        if not self._widget:
            ue.LogError("LoginPanel: CreateWidget returned None!")
            return

        # 绑定按钮事件
        try:
            self._widget.btn_login.OnClicked.Add(self._on_login_clicked)
            self._widget.btn_register.OnClicked.Add(self._on_register_clicked)
            self._widget.btn_open_level4.OnClicked.Add(self._on_open_level4)
        except Exception as e:
            ue.LogWarning(f"LoginPanel: Delegate binding failed ({e}), falling back to polling")

        # 显示到视口
        self._widget.bIsFocusable = True
        self._widget.AddToViewport(0)
        pc.bShowMouseCursor = True
        self._widget.SetKeyboardFocus()

        ue.LogWarning("LoginPanel: Shown")

    # ─── 按钮回调 ───

    def _on_login_clicked(self):
        """登录按钮点击"""
        if self._destroyed:
            return
        account = self._get_text("etb_account")
        password = self._get_text("etb_password")
        if not account or not password:
            self._set_status("Please enter account and password")
            return

        self._connect_and_action("Logging in...", lambda nm: nm.login(account, password))

    def _on_register_clicked(self):
        """注册按钮点击"""
        if self._destroyed:
            return
        account = self._get_text("etb_account")
        password = self._get_text("etb_password")
        if not account or not password:
            self._set_status("Please enter account and password")
            return

        self._connect_and_action("Registering...", lambda nm: nm.register(account, password))

    def _on_open_level4(self):
        """快捷进入Level4"""
        if self._destroyed:
            return
        self.destroy()
        ue.GameplayStatics.OpenLevel(self._parent, "Level4")

    # ─── 网络连接 ───

    def _connect_and_action(self, status_msg, action_fn):
        """连接服务器并执行动作"""
        from network.network_manager import NetworkManager
        nm = NetworkManager.get_instance()

        if nm.state != nm.STATE_DISCONNECTED:
            NetworkManager.reset_instance()
            nm = NetworkManager.get_instance()

        self._nm = nm

        # 注册回调
        nm.on_login_result = self._on_login_result
        nm.on_register_result = self._on_register_result
        nm.on_character_list = self._on_character_list
        nm.on_create_result = self._on_create_result
        nm.on_enter_game = self._on_enter_game

        if not nm.connect():
            self._set_status("Failed to connect to server")
            return

        self._set_status(status_msg)
        action_fn(nm)

    # ─── NetworkManager 回调 ───

    def _on_register_result(self, success, msg):
        if self._destroyed:
            return
        if success:
            self._set_status("Register success! Logging in...")
            account = self._get_text("etb_account")
            password = self._get_text("etb_password")
            if self._nm:
                self._nm.login(account, password)
        else:
            self._set_status(f"Register failed: {msg}")

    def _on_login_result(self, success, msg):
        if self._destroyed:
            return
        if success:
            self._set_status("Login success!")
            if self._nm:
                self._nm.get_characters()
        else:
            self._set_status(f"Login failed: {msg}")

    def _on_character_list(self, chars):
        """收到角色列表：通知 game_mode 显示主菜单"""
        if self._destroyed:
            return
        ue.LogWarning(f"LoginPanel: Got {len(chars)} characters")

        # 隐藏登录界面，通知 game_mode 显示主菜单并传入角色列表
        self._hide_widget()

        if self._on_login_success_callback:
            try:
                self._on_login_success_callback(chars)
            except Exception as e:
                ue.LogError(f"LoginPanel: on_login_success_callback error: {e}")

    def _on_create_result(self, success, char_info):
        """创角结果：由 MainMenuPanel 处理"""
        pass

    def _on_enter_game(self, player_id):
        """进入游戏：由 MainMenuPanel 处理"""
        pass

    # ─── 公开接口 ───

    def set_login_success_callback(self, callback):
        """设置登录成功后的回调（由 game_mode 注册，传入角色列表）"""
        self._on_login_success_callback = callback

    def destroy(self):
        """销毁登录界面"""
        if self._destroyed:
            return
        self._destroyed = True

        if self._nm:
            self._nm.on_login_result = None
            self._nm.on_register_result = None
            self._nm.on_character_list = None
            self._nm.on_create_result = None
            self._nm.on_enter_game = None

        if self._widget:
            try:
                self._widget.RemoveFromParent()
            except Exception:
                pass
            self._widget = None

        ue.LogWarning("LoginPanel: Destroyed")

    # ─── 内部工具 ───

    def _hide_widget(self):
        """隐藏 Widget（从视口移除但不销毁）"""
        if self._widget:
            try:
                self._widget.RemoveFromParent()
            except Exception:
                pass

    def _get_text(self, widget_name):
        """读取 EditableTextBox 的文本"""
        try:
            w = self._find_widget(widget_name)
            if w:
                text = w.GetText()
                return str(text).strip() if text else ""
        except Exception as e:
            ue.LogWarning(f"LoginPanel: _get_text({widget_name}) error: {e}")
        return ""

    def _clear_status(self, delta=0):
        """清空状态文本（由 AddTicker 延迟调用）"""
        if self._destroyed:
            return False
        try:
            w = self._find_widget("txt_status")
            if w:
                w.SetText("")
        except Exception:
            pass
        return False  # 一次性 ticker

    def _set_status(self, msg):
        """更新状态文本，5秒后自动清空"""
        try:
            w = self._find_widget("txt_status")
            if w:
                w.SetText(msg)
        except Exception as e:
            ue.LogWarning(f"LoginPanel: _set_status error: {e}")
        ue.LogWarning(f"LoginPanel: [STATUS] {msg}")
        # 5秒后自动清空
        ue.AddTicker(self._clear_status, 5.0)

    def _find_widget(self, name):
        """查找子控件：先尝试属性访问，再尝试 GetWidgetFromName"""
        if not self._widget:
            return None
        # 方式1：直接属性访问
        try:
            w = getattr(self._widget, name, None)
            if w:
                return w
        except Exception:
            pass
        # 方式2：GetWidgetFromName
        try:
            w = self._widget.GetWidgetFromName(name)
            if w:
                return w
        except Exception:
            pass
        return None

    _on_login_success_callback = None
