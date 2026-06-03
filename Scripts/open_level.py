"""在UE编辑器中打开指定关卡

用法：在UE编辑器的 Output Log (Cmd) 中运行：
    py "Scripts/open_level.py" Level3
    py "Scripts/open_level.py" Level4
    py "Scripts/open_level.py" MainMenu
"""

import sys
import unreal

if len(sys.argv) < 2:
    unreal.log_error("open_level: 请传入关卡名，例如 py \"Scripts/open_level.py\" Level3")
else:
    level_name = sys.argv[1]
    # MainMenu 在 /Game/ 下，其余在 /Game/Maps/ 下
    if level_name == "MainMenu":
        level_path = f"/Game/{level_name}"
    else:
        level_path = f"/Game/Maps/{level_name}"
    unreal.log(f"open_level: 正在打开 {level_path} ...")
    unreal.EditorLevelLibrary.load_level(level_path)
    unreal.log(f"open_level: 已打开 {level_name}")
