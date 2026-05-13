# -*- encoding: utf-8 -*-
"""Tickable Mixin — 为 NePy Subclassing Actor 提供 Tick 能力

NePy Subclassing 不支持覆写 ReceiveTick：
  UE 优化：蓝图中没有 Tick 节点 → C++ 层不注册 Ticker → ReceiveTick 永远不被调用。
  参考：NEPYDoc/game-developing/ticker-and-timer.md

解决方案：使用 ue.AddTicker 替代 ReceiveTick。

用法:
    @ue.uclass()
    class MyActor(ue.Actor, TickableMixin):
        def __init_pyobj__(self):
            self._ticker_handle = None

        @ue.ufunction(override=True)
        def ReceiveBeginPlay(self):
            self._start_ticker()

        def on_tick(self, delta_time):
            # 覆写此方法实现每帧逻辑
            pass

        def ReceiveEndPlay(self, end_type):
            # 必须调用 _stop_ticker，否则 ticker 回调会在 Actor 销毁后继续执行
            self._stop_ticker()
"""

import ue


class TickableMixin:
    """为 NePy Subclassing Actor 提供 Tick 能力的 Mixin

    注意：
    1. ue.Actor 必须是第一个基类，Mixin 放后面：
        class MyActor(ue.Actor, TickableMixin)  ✓
        class MyActor(TickableMixin, ue.Actor)  ✗
    2. 必须在 ReceiveEndPlay 中调用 _stop_ticker()，否则 Actor 销毁后
       ticker 回调仍会执行并抛 RuntimeError
    """

    def _start_ticker(self):
        """在 ReceiveBeginPlay 中调用，启动每帧回调"""
        if getattr(self, '_ticker_handle', None):
            return
        self._ticker_stopped = False
        self._ticker_handle = ue.AddTicker(self._on_ticker)

    def _stop_ticker(self):
        """在 ReceiveEndPlay 或 Actor 销毁前调用，停止 ticker"""
        self._ticker_stopped = True
        handle = getattr(self, '_ticker_handle', None)
        if handle:
            ue.RemoveTicker(handle)
            self._ticker_handle = None

    def _on_ticker(self, delta_time):
        if getattr(self, '_ticker_stopped', True):
            return False
        try:
            self.on_tick(delta_time)
        except RuntimeError:
            # Actor 已被引擎销毁（关卡卸载、游戏结束等），停止 ticker
            self._stop_ticker()
            return False
        return True

    def on_tick(self, delta_time):
        """子类覆写此方法实现每帧逻辑（替代 ReceiveTick）"""
        pass
