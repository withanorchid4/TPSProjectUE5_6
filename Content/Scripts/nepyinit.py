# -*- encoding: utf-8 -*-
"""NePy 初始化脚本"""

import ue
import traceback


def on_init():
    """NePy 插件初始化时调用"""
    ue.LogWarning('NePy initialized!')
    
    # 注册 Python 类（必须在 on_init 中导入，才能作为 Blueprint 基类）
    # 注意：character 是目录包，tps_character 是文件
    try:
        import tps_character
        ue.LogWarning('tps_character module loaded successfully!')
    except Exception as e:
        ue.LogError(f'Failed to load tps_character: {e}')
        import traceback
        traceback.print_exc()
    
    if ue.GIsEditor:
        # 编辑器模式：启动热重载监控
        try:
            import reload_monitor
            reload_monitor.start()
        except:
            traceback.print_exc()
        
        # 启动 GM 命令调试
        try:
            import gmcmds
            gmcmds.debug()
        except:
            traceback.print_exc()


def on_post_engine_init():
    """引擎初始化完成后调用"""
    ue.LogWarning('Post engine init - loading character module')
    
    # 初始化动态输入映射（无需编辑器配置）
    import input_config
    input_config.InputConfig.setup()
    
    # 加载角色模块（在此处加载避免 AssetRegistry 时序问题）
    import character


def on_shutdown():
    """NePy 插件关闭时调用"""
    ue.LogWarning('NePy shutdown!')


def on_debug_input(cmd_str):
    """处理调试输入"""
    import gmcmds
    return gmcmds.handle_debug_input(cmd_str)


def on_tick(dt):
    """每帧调用"""
    pass
