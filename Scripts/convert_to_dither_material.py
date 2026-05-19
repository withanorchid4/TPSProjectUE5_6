"""
=========================================================
 虚幻引擎一键复制并改造 Dither 材质脚本 (全自动终极版)
=========================================================
 使用方法：
 1. 找到你要改造的【原材质】路径（右键 -> Copy Reference）。
 2. 规划好你要生成的【新 Dither 材质】的路径和名字。
 3. 修改本脚本最底部的 ORIGINAL_MATERIAL 和 TARGET_MATERIAL。
 4. 在 UE 的 Output Log (输出日志) 中运行此脚本。
=========================================================
"""

import unreal

def create_dither_material(original_mat_path, new_dither_mat_path):
    """自动复制并进行 Dither 核心改造函数"""
    
    # ==========================================
    # 1. 自动复制与资产加载逻辑
    # ==========================================
    # 检查目标路径是否已经存在资产
    if unreal.EditorAssetLibrary.does_asset_exist(new_dither_mat_path):
        unreal.log_warning(f"⚠️ 目标资产已存在，将直接加载并覆写节点: {new_dither_mat_path}")
        new_mat = unreal.EditorAssetLibrary.load_asset(new_dither_mat_path)
    else:
        # 不存在则从原材质复制一份
        new_mat = unreal.EditorAssetLibrary.duplicate_asset(original_mat_path, new_dither_mat_path)
        if new_mat:
            unreal.log(f"📄 成功复制原材质并创建新资产: {new_dither_mat_path}")

    # 容错校验
    if not new_mat:
        unreal.log_error(f"❌ 材质获取/复制失败！请检查原材质路径是否拼写正确: {original_mat_path}")
        return  # 安全退出

    # ==========================================
    # 2. 材质核心改造逻辑
    # ==========================================
    # 【极其关键】修改为 Masked 模式，强制引擎解锁 Opacity Mask 引脚
    new_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)

    # 3. 创建 FadeOpacity 标量参数节点
    fade_param_node = unreal.MaterialEditingLibrary.create_material_expression(
        new_mat,
        unreal.MaterialExpressionScalarParameter,
        -400, 200
    )
    fade_param_node.set_editor_property("parameter_name", "FadeOpacity")
    fade_param_node.set_editor_property("default_value", 0.5)

    # 4. 创建并加载 DitherTemporalAA 材质函数
    # 4.1 创建一个通用的“材质函数调用”节点
    dither_node = unreal.MaterialEditingLibrary.create_material_expression(
        new_mat, 
        unreal.MaterialExpressionMaterialFunctionCall, 
        -200, 200
    )
        
    # 4.2 加载引擎底层的 Dither 资产
    dither_function = unreal.EditorAssetLibrary.load_asset("/Engine/Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA")
    if not dither_function:
        unreal.log_error("❌ 找不到 DitherTemporalAA 引擎资产，请检查引擎内容是否完整！")
        return  # 安全退出

    # 4.3 赋予调用节点
    dither_node.set_editor_property("material_function", dither_function)

    # 5. 开始连线 (使用底层真实引脚名称)
    # 连线 1：FadeOpacity → DitherTemporalAA.Alpha Threshold
    unreal.MaterialEditingLibrary.connect_material_expressions(
        fade_param_node, "",
        dither_node, "Alpha Threshold"  # 绝对正确的真名
    )

    # 连线 2：DitherTemporalAA → 主材质节点的 Opacity Mask
    unreal.MaterialEditingLibrary.connect_material_property(
        dither_node, "",
        unreal.MaterialProperty.MP_OPACITY_MASK
    )

    # 6. 刷新、编译并保存资产
    unreal.log("🔄 正在重新编译着色器，请稍候...")
    unreal.MaterialEditingLibrary.recompile_material(new_mat)
    unreal.EditorAssetLibrary.save_loaded_asset(new_mat)

    unreal.log(f"✅ 材质 Dither 自动化改造大功告成: {new_dither_mat_path}")


if __name__ == "__main__":
    ORIGINAL_MATERIAL = "/Game/LowerSector_Mod/Models/SkyTower/Materials/M_SkyTower"
    TARGET_MATERIAL = "/Game/LowerSector_Mod/Models/SkyTower/Materials/M_SkyTower_Dither"
    create_dither_material(ORIGINAL_MATERIAL, TARGET_MATERIAL)