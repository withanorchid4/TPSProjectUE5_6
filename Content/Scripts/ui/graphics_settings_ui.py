# -*- encoding: utf-8 -*-
"""GraphicsSettingsPanel — 画面设置界面控制器

控制 WBP_GraphicsSettings：提供 Low/Med/High 三档画质设置，显示当前状态，
支持切换画质并返回。

WBP_GraphicsSettings 需要的命名控件：
- btn_low   — Button，设置 Low 画质
- btn_med   — Button，设置 Med 画质
- btn_high  — Button，设置 High 画质
- btn_back  — Button，返回上一界面
- txt_current — TextBlock，显示当前画质状态
"""

import ue
from system.graphics_quality_manager import GraphicsQualityManager


class GraphicsSettingsPanel:
    """画面设置面板控制器

    职责：
    - 创建 WBP_GraphicsSettings Widget 并添加到视口
    - 绑定画质切换按钮事件
    - 显示当前画质状态
    - 高亮当前选中的画质按钮
    - 提供返回按钮回调
    """

    # Widget 蓝图路径
    WBP_PATH = "/Game/BluePrint/WBP_GraphicsSettings.WBP_GraphicsSettings_C"

    def __init__(self, parent, pc):
        """
        Args:
            parent: UObject 上下文（通常是 GameMode）
            pc: PlayerController
        """
        self._parent = parent
        self._pc = pc
        self._widget = None
        self._gqm = None
        self._destroyed = False
        self._on_back_callback = None

        # 创建 Widget
        widget_class = ue.LoadObject(ue.Class, self.WBP_PATH)
        if not widget_class:
            ue.LogError("GraphicsSettingsPanel: Failed to load WBP_GraphicsSettings_C!")
            return

        self._widget = ue.WidgetBlueprintLibrary.Create(parent, widget_class, pc)
        if not self._widget:
            ue.LogError("GraphicsSettingsPanel: CreateWidget returned None!")
            return

        # 获取 GraphicsQualityManager 单例
        self._gqm = GraphicsQualityManager.get_instance()

        # 绑定按钮事件
        try:
            self._widget.btn_low.OnClicked.Add(self._on_low_clicked)
            self._widget.btn_med.OnClicked.Add(self._on_med_clicked)
            self._widget.btn_high.OnClicked.Add(self._on_high_clicked)
            self._widget.btn_back.OnClicked.Add(self._on_back_clicked)
        except Exception as e:
            ue.LogWarning(f"GraphicsSettingsPanel: Delegate binding failed ({e}), falling back to polling")

        # 更新显示（显示当前画质状态和高亮按钮）
        self._update_display()

        # 显示到视口
        self._widget.bIsFocusable = True
        self._widget.AddToViewport(0)
        pc.bShowMouseCursor = True
        self._widget.SetKeyboardFocus()

        ue.LogWarning("GraphicsSettingsPanel: Shown")

    # ─── 按钮回调 ───

    def _on_low_clicked(self):
        """Low 画质按钮点击"""
        if self._destroyed or not self._gqm:
            return
        self._gqm.set_quality(GraphicsQualityManager.QUALITY_LOW)
        self._update_display()

    def _on_med_clicked(self):
        """Med 画质按钮点击"""
        if self._destroyed or not self._gqm:
            return
        self._gqm.set_quality(GraphicsQualityManager.QUALITY_MED)
        self._update_display()

    def _on_high_clicked(self):
        """High 画质按钮点击"""
        if self._destroyed or not self._gqm:
            return
        self._gqm.set_quality(GraphicsQualityManager.QUALITY_HIGH)
        self._update_display()

    def _on_back_clicked(self):
        """返回按钮点击"""
        if self._destroyed:
            return
        if self._on_back_callback:
            try:
                self._on_back_callback()
            except Exception as e:
                ue.LogError(f"GraphicsSettingsPanel: on_back_callback error: {e}")

    # ─── 显示更新 ───

    def _update_display(self):
        """更新显示：txt_current 状态文本 + 按钮高亮标记"""
        if not self._widget or not self._gqm:
            return

        current_quality = self._gqm.current_quality
        current_name = self._gqm.current_quality_name

        # 更新状态文本
        try:
            txt_current = self._find_widget("txt_current")
            if txt_current:
                txt_current.SetText(f"当前画质: {current_name}")
        except Exception as e:
            ue.LogWarning(f"GraphicsSettingsPanel: Failed to update txt_current: {e}")

        # 按钮高亮：选中项文本加 [ ] 标记
        button_map = {
            GraphicsQualityManager.QUALITY_LOW: ("btn_low", "Low"),
            GraphicsQualityManager.QUALITY_MED: ("btn_med", "Med"),
            GraphicsQualityManager.QUALITY_HIGH: ("btn_high", "High"),
        }

        for level, (btn_name, label) in button_map.items():
            try:
                btn = self._find_widget(btn_name)
                if btn and hasattr(btn, 'SetText'):
                    if level == current_quality:
                        btn.SetText(f"[ {label} ]")
                    else:
                        btn.SetText(label)
            except Exception:
                pass

    # ─── 公开接口 ───

    def set_back_callback(self, callback):
        """设置返回按钮回调

        Args:
            callback: 返回按钮点击时调用的函数
        """
        self._on_back_callback = callback

    def destroy(self):
        """销毁画面设置界面"""
        if self._destroyed:
            return
        self._destroyed = True

        # 清理回调引用
        self._on_back_callback = None

        # 从视口移除 Widget
        if self._widget:
            try:
                self._widget.RemoveFromParent()
            except Exception:
                pass
            self._widget = None

        ue.LogWarning("GraphicsSettingsPanel: Destroyed")

    # ─── 内部工具 ───

    def _find_widget(self, name):
        """查找子控件：先尝试属性访问，再尝试 GetWidgetFromName

        Args:
            name: Widget 名称

        Returns:
            Widget 对象或 None
        """
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
