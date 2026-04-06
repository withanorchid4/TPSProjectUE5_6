# -*- encoding: utf-8 -*-
"""
输入配置 - 动态创建 Input Mappings

B1 方式：Python 代码动态添加 Axis/Action Mappings
无需在编辑器中手动配置项目设置

使用方法：
    InputConfig.setup()  # 在游戏初始化时调用一次
"""

import ue


class InputConfig:
    """
    输入配置管理器
    
    使用 ue.GetInputSettings() 动态添加 Axis/Action Mappings
    完全不需要在编辑器中手动配置
    """
    
    _initialized = False
    
    # ========================================
    # Axis Mappings 定义
    # ========================================
    AXIS_MAPPINGS = [
        # 移动轴
        {"AxisName": "MoveForward", "Key": "W", "Scale": 1.0},
        {"AxisName": "MoveForward", "Key": "S", "Scale": -1.0},
        {"AxisName": "MoveRight", "Key": "D", "Scale": 1.0},
        {"AxisName": "MoveRight", "Key": "A", "Scale": -1.0},
        # 视角轴
        {"AxisName": "Turn", "Key": "MouseX", "Scale": 1.0},
        {"AxisName": "LookUp", "Key": "MouseY", "Scale": -1.0},
    ]
    
    # ========================================
    # Action Mappings 定义
    # ========================================
    ACTION_MAPPINGS = [
        {"ActionName": "Jump", "Key": "SpaceBar"},
        {"ActionName": "Fire", "Key": "LeftMouseButton"},
        {"ActionName": "Aim", "Key": "RightMouseButton"},
    ]
    
    @classmethod
    def setup(cls, force: bool = False):
        """
        设置输入映射
        
        在游戏初始化时调用一次，动态添加所有 Axis/Action Mappings
        
        Args:
            force: 强制重新初始化
        """
        if cls._initialized and not force:
            ue.Log("InputConfig: Already initialized")
            return
        
        if force:
            cls._initialized = False
        
        ue.Log("InputConfig: Setting up dynamic input mappings...")
        
        # 获取 InputSettings（静态方法）
        input_settings = ue.InputSettings.GetInputSettings()
        if not input_settings:
            ue.LogError("InputConfig: Failed to get InputSettings!")
            return
        
        # 添加 Axis Mappings
        for mapping in cls.AXIS_MAPPINGS:
            cls._add_axis_mapping(input_settings, mapping)
        
        # 添加 Action Mappings
        for mapping in cls.ACTION_MAPPINGS:
            cls._add_action_mapping(input_settings, mapping)
        
        # 强制重建按键映射
        input_settings.ForceRebuildKeymaps()
        
        cls._initialized = True
        ue.LogWarning("InputConfig: Dynamic input mappings complete!")
    
    @classmethod
    def _add_axis_mapping(cls, input_settings, mapping: dict):
        """
        添加轴映射
        
        Args:
            input_settings: ue.InputSettings 实例
            mapping: {"AxisName": str, "Key": str, "Scale": float}
        """
        axis_name = mapping["AxisName"]
        key_name = mapping["Key"]
        scale = mapping.get("Scale", 1.0)
        
        try:
            # 创建 InputAxisKeyMapping
            axis_mapping = ue.InputAxisKeyMapping()
            axis_mapping.AxisName = axis_name
            axis_mapping.Key = ue.Key(key_name)
            axis_mapping.Scale = scale
            
            # 添加到 InputSettings
            input_settings.AddAxisMapping(axis_mapping, True)
            ue.Log(f"  Added Axis: {axis_name} <- {key_name} (scale: {scale})")
            
        except Exception as e:
            ue.LogWarning(f"  Failed to add axis {axis_name}: {e}")
    
    @classmethod
    def _add_action_mapping(cls, input_settings, mapping: dict):
        """
        添加动作映射
        
        Args:
            input_settings: ue.InputSettings 实例
            mapping: {"ActionName": str, "Key": str}
        """
        action_name = mapping["ActionName"]
        key_name = mapping["Key"]
        
        try:
            # 创建 InputActionKeyMapping
            action_mapping = ue.InputActionKeyMapping()
            action_mapping.ActionName = action_name
            action_mapping.Key = ue.Key(key_name)
            
            # 添加到 InputSettings
            input_settings.AddActionMapping(action_mapping, True)
            ue.Log(f"  Added Action: {action_name} <- {key_name}")
            
        except Exception as e:
            ue.LogWarning(f"  Failed to add action {action_name}: {e}")
    
    @classmethod
    def is_initialized(cls) -> bool:
        """检查是否已初始化"""
        return cls._initialized