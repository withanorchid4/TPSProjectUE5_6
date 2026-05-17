# -*- encoding: utf-8 -*-
"""GraphicsQualityManager — 画面质量管理器（单例）

通过写 GameUserSettings.ini + GameUserSettings.ApplySettings 设置画质。
零耦合设计，不依赖任何其他游戏模块。

用法:
    from system.graphics_quality_manager import GraphicsQualityManager
    gqm = GraphicsQualityManager.get_instance()
    gqm.initialize()
    gqm.set_quality(0)  # Low
    gqm.set_quality(2)  # High
"""

import ue


class GraphicsQualityManager:
    """画面质量管理器

    提供 Low(0) / Med(1) / High(2) 三档画质设置。
    通过直接写 GameUserSettings.ini 的 ScalabilityQuality 段，
    然后调 GameUserSettings.LoadConfig() + ApplySettings(True) 使其生效。
    """

    QUALITY_LOW = 0
    QUALITY_MED = 1
    QUALITY_HIGH = 2

    QUALITY_NAMES = {0: "Low", 1: "Med", 2: "High"}

    # 每个 Scalability 组在各档位的值
    # (组名, Low值, Med值, High值)
    SCALABILITY_GROUPS = [
        ("ResolutionQuality",       70,   90, 100),
        ("ViewDistanceQuality",      0,    1,   2),
        ("AntiAliasingQuality",      0,    1,   2),
        ("ShadowQuality",            0,    1,   2),
        ("GlobalIlluminationQuality",0,    1,   2),
        ("ReflectionQuality",        0,    1,   2),
        ("PostProcessQuality",       0,    1,   2),
        ("TextureQuality",           0,    1,   2),
        ("EffectsQuality",           0,    1,   2),
        ("FoliageQuality",           0,    1,   2),
    ]

    def __init__(self):
        self._current_quality = self.QUALITY_HIGH
        self._ini_path = None

    # ─── 单例 ───

    _instance = None

    @staticmethod
    def get_instance():
        if GraphicsQualityManager._instance is None:
            GraphicsQualityManager._instance = GraphicsQualityManager()
        return GraphicsQualityManager._instance

    @staticmethod
    def reset_instance():
        GraphicsQualityManager._instance = None

    # ─── 公开 API ───

    @property
    def current_quality(self):
        return self._current_quality

    @property
    def current_quality_name(self):
        return self.QUALITY_NAMES.get(self._current_quality, "Unknown")

    def initialize(self):
        """初始化：定位 ini 文件，读取已保存的档位"""
        import os
        # 从 __file__ 推导项目根目录（本脚本位于 Content/Scripts/system/）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.normpath(os.path.join(script_dir, "..", "..", ".."))
        self._ini_path = os.path.join(
            project_root, "Saved", "Config", "WindowsEditor", "GameUserSettings.ini"
        )
        self._load_saved_quality()
        ue.LogWarning(f"GraphicsQualityManager: Initialized, path={self._ini_path}, current={self.current_quality_name}")
        return True

    def set_quality(self, level):
        """设置画质档位（0=Low, 1=Med, 2=High）

        写入 GameUserSettings.ini 的 ScalabilityQuality 段，
        然后让 GameUserSettings 重新加载并应用。
        """
        if level not in self.QUALITY_NAMES:
            ue.LogError(f"GraphicsQualityManager: Invalid quality level {level}")
            return False

        # 自动初始化兜底
        if not self._ini_path:
            self.initialize()

        if not self._ini_path:
            ue.LogError("GraphicsQualityManager: set_quality failed: ini_path still not set after initialize()")
            return False

        try:
            # 1. 先更新档位，供 _apply 读取
            self._current_quality = level

            # 2. 写 ini 文件（持久化）
            self._write_scalability_to_ini(level)

            # 3. 运行时生效
            self._apply_via_game_user_settings()
            ue.LogWarning(f"GraphicsQualityManager: Set quality to {self.QUALITY_NAMES[level]} ({level})")
            return True

        except Exception as e:
            ue.LogError(f"GraphicsQualityManager: set_quality failed: {e}")
            return False

    # ─── 内部实现 ───

    def _write_scalability_to_ini(self, level):
        """将 ScalabilityQuality 段写入 GameUserSettings.ini"""
        import os
        ini_path = self._ini_path
        if not ini_path:
            raise RuntimeError("ini_path not set, call initialize() first")

        # 读取现有内容
        lines = []
        if os.path.exists(ini_path):
            with open(ini_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        # 移除旧的 ScalabilityQuality 段
        filtered = []
        in_section = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[/Script/Engine.GameUserSettings]"):
                in_section = True
                filtered.append(line)
                continue
            if stripped.startswith("["):
                in_section = False
            # 跳过旧的 ScalabilityQuality 行
            if in_section and any(
                stripped.startswith(f"{group_name}=")
                for group_name, _, _, _ in self.SCALABILITY_GROUPS
            ):
                continue
            filtered.append(line)

        # 在 [/Script/Engine.GameUserSettings] 段末尾插入 ScalabilityQuality
        result = []
        inserted = False
        for line in filtered:
            result.append(line)
            if not inserted and line.strip().startswith("[/Script/Engine.GameUserSettings]"):
                # 在段头之后立即插入
                for group_name, low_val, med_val, high_val in self.SCALABILITY_GROUPS:
                    values = [low_val, med_val, high_val]
                    result.append(f"{group_name}={values[level]}\n")
                inserted = True

        with open(ini_path, "w", encoding="utf-8") as f:
            f.writelines(result)

        ue.Log(f"GraphicsQualityManager: Written ScalabilityQuality to {ini_path}")

    def _apply_via_game_user_settings(self):
        """通过控制台命令统一应用 Scalability 设置

        所有组统一使用 sg.XxxQuality 控制台命令，确保优先级一致（均为 SetByConsole），
        避免 SetByScalability 与 SetByConsole 优先级冲突。
        """
        import system.game_mode as gm
        ctx = gm._instance
        if not ctx:
            ue.LogWarning("GraphicsQualityManager: GameMode not available")
            return

        level = self._current_quality

        for group_name, low_val, med_val, high_val in self.SCALABILITY_GROUPS:
            if group_name == "ResolutionQuality":
                # ResolutionQuality 取百分比而非 0-2，用 r.ScreenPercentage
                cmd = f"r.ScreenPercentage {high_val if level == 2 else med_val if level == 1 else low_val}"
            else:
                cmd = f"sg.{group_name} {level}"

            try:
                ue.KismetSystemLibrary.ExecuteConsoleCommand(ctx, cmd)
            except Exception as e:
                ue.LogWarning(f"GQM: console '{cmd}' failed: {e}")

        ue.LogWarning(f"GraphicsQualityManager: Applied quality={self.current_quality_name} via console commands")

    def _apply_missing_groups_via_cvar(self, groups):
        """已废弃，保留空实现以防调用"""
        pass

    def _load_saved_quality(self):
        """从 GameUserSettings.ini 读取已保存的 ScalabilityQuality"""
        import os
        ini_path = self._ini_path
        if not ini_path or not os.path.exists(ini_path):
            return

        try:
            with open(ini_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ShadowQuality="):
                        saved = int(line.split("=")[1])
                        if saved in self.QUALITY_NAMES:
                            self._current_quality = saved
                        return
        except Exception:
            pass
