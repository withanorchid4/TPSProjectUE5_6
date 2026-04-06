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
        
        ue.LogWarning("KeyboardInputHandler: Bound!")
    
    def unbind(self):
        """解绑输入"""
        self._move_forward = 0.0
        self._move_right = 0.0
        self._turn_rate = 0.0
        self._look_up_rate = 0.0
        self._is_firing = False
        ue.Log("KeyboardInputHandler: Unbound")
    
    def tick(self, delta_time: float):
        """每帧更新"""
        # 应用移动
        if self.movement:
            if self._move_forward != 0.0:
                self.movement.move_forward(self._move_forward)
            if self._move_right != 0.0:
                self.movement.move_right(self._move_right)
        
        # 应用视角
        if self.camera:
            if self._turn_rate != 0.0:
                self.camera.update_rotation(self._turn_rate * delta_time * 100.0, 0.0)
            if self._look_up_rate != 0.0:
                self.camera.update_rotation(0.0, self._look_up_rate * delta_time * 100.0)
        
        # 射击
        if self._is_firing and self.shooting:
            self.shooting.shoot()
    
    # === Axis 回调 ===
    
    def _on_move_forward(self, value: float):
        self._move_forward = value
    
    def _on_move_right(self, value: float):
        self._move_right = value
    
    def _on_turn(self, value: float):
        self._turn_rate = value
    
    def _on_look_up(self, value: float):
        self._look_up_rate = value
    
    # === Action 回调 ===
    
    def _on_jump(self):
        if self.movement:
            self.movement.jump()
    
    def _on_fire_start(self):
        self._is_firing = True
        if self.shooting:
            self.shooting.start_firing()
    
    def _on_fire_stop(self):
        self._is_firing = False
        if self.shooting:
            self.shooting.stop_firing()
    
    def _on_aim_start(self):
        if self.camera:
            self.camera.set_aiming(True)
    
    def _on_aim_stop(self):
        if self.camera:
            self.camera.set_aiming(False)