# -*- encoding: utf-8 -*-
"""
键盘/鼠标输入处理器 - 使用 UE InputComponent 动态绑定

B1 方式：配合 InputConfig 动态添加的 Axis/Action Mappings
"""

import ue
from character.input_handler import InputHandler


class KeyboardInputHandler(InputHandler):
    """
    键盘/鼠标输入处理器
    
    使用 InputComponent 绑定 InputConfig 动态创建的 Axis/Action Mappings
    """
    
    def __init__(self, owner):
        super().__init__(owner)
        
        # 输入值缓存
        self._move_forward = 0.0
        self._move_right = 0.0
        self._turn_rate = 0.0
        self._look_up_rate = 0.0
        self._is_firing = False
        self._menu_open = False  # 画质菜单打开时抑制游戏输入
        
        # 玩家控制器
        self._pc = None
    
    def bind(self):
        """绑定输入事件"""
        self._pc = self.owner.GetController()
        if not self._pc:
            ue.LogWarning("KeyboardInputHandler: No controller!")
            return
        
        self.owner.EnableInput(self._pc)
        
        input_comp = self.owner.InputComponent
        if not input_comp:
            ue.LogError("KeyboardInputHandler: No InputComponent!")
            return
        
        ue.Log("KeyboardInputHandler: Binding inputs...")
        
        # === 绑定 Axis ===
        input_comp.BindAxis("MoveForward", self._on_move_forward)
        input_comp.BindAxis("MoveRight", self._on_move_right)
        input_comp.BindAxis("Turn", self._on_turn)
        input_comp.BindAxis("LookUp", self._on_look_up)
        
        # === 绑定 Action ===
        input_comp.BindAction("Jump", ue.EInputEvent.IE_Pressed, self._on_jump)
        input_comp.BindAction("Fire", ue.EInputEvent.IE_Pressed, self._on_fire_start)
        input_comp.BindAction("Fire", ue.EInputEvent.IE_Released, self._on_fire_stop)
        input_comp.BindAction("Aim", ue.EInputEvent.IE_Pressed, self._on_aim_start)
        input_comp.BindAction("Aim", ue.EInputEvent.IE_Released, self._on_aim_stop)
        input_comp.BindAction("Sprint", ue.EInputEvent.IE_Pressed, self._on_sprint_start)
        input_comp.BindAction("Sprint", ue.EInputEvent.IE_Released, self._on_sprint_stop)
        input_comp.BindAction("ToggleFireMode", ue.EInputEvent.IE_Pressed, self._on_toggle_fire_mode)
        input_comp.BindAction("SwitchWeapon", ue.EInputEvent.IE_Pressed, self._on_switch_weapon)
        input_comp.BindAction("MagicArrow", ue.EInputEvent.IE_Pressed, self._on_magic_arrow)
        input_comp.BindAction("Reload", ue.EInputEvent.IE_Pressed, self._on_reload)
        input_comp.BindAction("SelfBuff", ue.EInputEvent.IE_Pressed, self._on_self_buff)
        input_comp.BindAction("GraphicsMenu", ue.EInputEvent.IE_Pressed, self._on_graphics_menu)
        
        ue.LogWarning("KeyboardInputHandler: Input bindings complete!")
    
    def unbind(self):
        """解绑输入"""
        self._move_forward = 0.0
        self._move_right = 0.0
        self._turn_rate = 0.0
        self._look_up_rate = 0.0
        self._is_firing = False
        ue.Log("KeyboardInputHandler: Unbound")
    
    def tick(self, delta_time: float):
        """
        每帧更新
        
        Args:
            delta_time: 帧间隔时间
        """
        # 画质菜单打开时抑制游戏输入
        if self._menu_open:
            return

        # 应用移动
        if self.movement:
            if self._move_forward != 0.0:
                self.movement.move_forward(self._move_forward)
            if self._move_right != 0.0:
                self.movement.move_right(self._move_right)
        
        # 应用视角旋转
        if self.camera:
            if self._turn_rate != 0.0:
                self.camera.update_rotation(self._turn_rate, 0.0)
            if self._look_up_rate != 0.0:
                self.camera.update_rotation(0.0, self._look_up_rate)
        
        # 更新射击组件（连射 + 换弹计时）
        if self.shooting:
            self.shooting.tick(delta_time)
    
    # === Axis 回调 ===
    
    def _on_move_forward(self, value: float):
        """前后移动回调"""
        self._move_forward = value
    
    def _on_move_right(self, value: float):
        """左右移动回调"""
        self._move_right = value
    
    def _on_turn(self, value: float):
        """水平旋转回调"""
        self._turn_rate = value
    
    def _on_look_up(self, value: float):
        """垂直旋转回调"""
        self._look_up_rate = value
    
    # === Action 回调 ===
    
    def _on_jump(self):
        """跳跃回调"""
        if self.movement:
            self.movement.jump()
    
    def _on_fire_start(self):
        """开始射击回调"""
        self._is_firing = True
        if self.shooting:
            self.shooting.start_firing()

    def _on_fire_stop(self):
        """停止射击回调"""
        self._is_firing = False
        if self.shooting:
            self.shooting.stop_firing()

    def _on_aim_start(self):
        """开始瞄准回调"""
        if self.camera:
            self.camera.set_aiming(True)
        # 网络同步：瞄准开始
        self._send_action("aim_start")

    def _on_aim_stop(self):
        """停止瞄准回调"""
        if self.camera:
            self.camera.set_aiming(False)
        # 网络同步：瞄准结束
        self._send_action("aim_end")

    def _on_sprint_start(self):
        """开始冲刺回调"""
        if self.movement:
            self.movement.start_sprint()

    def _on_sprint_stop(self):
        """停止冲刺回调"""
        if self.movement:
            self.movement.stop_sprint()

    def _on_toggle_fire_mode(self):
        """切换射击模式回调"""
        if self.shooting:
            self.shooting.toggle_fire_mode()

    def _on_switch_weapon(self):
        """切换持枪/收枪回调"""
        self.owner.switch_weapon()
    
    def _on_magic_arrow(self):
        """发射魔法箭"""
        if self.shooting:
            self.shooting.fire_magic_arrow()
    
    def _on_reload(self):
        """手动换弹"""
        if self.shooting:
            self.shooting.start_reload()
    
    def _on_self_buff(self):
        """给自己添加增攻Buff"""
        if hasattr(self.owner, 'self_buff'):
            self.owner.self_buff()
    
    def _on_graphics_menu(self):
        """切换画质设置菜单"""
        import system.game_mode as gm
        if gm._instance:
            gm._instance.toggle_graphics_settings_in_game()

    def set_menu_open(self, is_open: bool):
        """设置画质菜单开关状态，打开时清零输入缓存"""
        self._menu_open = is_open
        if is_open:
            self._move_forward = 0.0
            self._move_right = 0.0
            self._turn_rate = 0.0
            self._look_up_rate = 0.0
            self._is_firing = False
    
    # ─── 网络同步 ───

    def _send_action(self, action_name):
        """发送动作同步到服务器"""
        try:
            from network.network_manager import NetworkManager
            from network.proto import tps_pb2
            nm = NetworkManager.get_instance()
            if nm.is_in_game:
                action_map = {
                    "reload_start": tps_pb2.ACTION_RELOAD_START,
                    "reload_end": tps_pb2.ACTION_RELOAD_END,
                    "aim_start": tps_pb2.ACTION_AIM_START,
                    "aim_end": tps_pb2.ACTION_AIM_END,
                }
                action_type = action_map.get(action_name)
                if action_type is not None:
                    nm.send_action(action_type)
        except Exception:
            pass
