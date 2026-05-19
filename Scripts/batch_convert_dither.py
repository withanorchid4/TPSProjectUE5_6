"""
批量扫描 /Game/LowerSector_Mod/Models 下所有材质，
为每个材质创建 Dither 版本，并输出映射关系到 MD 文件。

使用方法：
  在 UE 编辑器的 Output Log (Cmd) 中执行：
  py "C:/Users/zilong.luo/Desktop/netease/NeteaseDocs/nepy_mini_NoSC/nepy_mini/Newbie/Scripts/batch_convert_dither.py"
"""

import unreal
import os

# ============ 配置 ============
SCAN_PATH = "/Game/LowerSector_Mod/Models"
MAPPING_OUTPUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "docs", "dither_material_mapping.md"
)
# ===============================

# 导入转换函数
import sys
scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from convert_to_dither_material import create_dither_material


def collect_materials(scan_path):
    """递归收集指定路径下所有 Material 资产的路径"""
    materials = []
    assets = unreal.EditorAssetLibrary.list_assets(scan_path, recursive=True, include_folder=False)
    for asset_path in assets:
        # asset_path 格式: /Game/.../M_Foo.M_Foo
        # 加载判断类型
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if asset and isinstance(asset, unreal.MaterialInterface) and not isinstance(asset, unreal.MaterialInstanceConstant):
            # 只处理母材质，跳过 MaterialInstance
            # asset_path 形如 "/Game/X/M_Foo.M_Foo"，取去掉对象名部分作为材质路径
            material_path = asset_path.rsplit(".", 1)[0]
            # 跳过已经是 Dither 版本的
            if material_path.endswith("_Dither"):
                unreal.log(f"⏭️ 跳过已有 Dither 材质: {material_path}")
                continue
            materials.append(material_path)
    return materials


def generate_dither_path(orig_path):
    """从原材质路径生成 Dither 版本路径
    
    /Game/X/Materials/M_Foo → /Game/X/Materials/M_Foo_Dither
    """
    return orig_path + "_Dither"


def write_mapping_md(mapping, output_path):
    """将映射关系写入 MD 文件"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Dither Material Mapping\n\n")
        f.write("Original → Dither material path mapping (for dither_occlusion.py)\n\n")
        f.write("```python\n")
        f.write("DITHER_MAT_MAP = {\n")
        for orig, dither in sorted(mapping.items()):
            f.write(f'    "{orig}": "{dither}",\n')
        f.write("}\n")
        f.write("```\n")
    unreal.log(f"📝 映射文件已写入: {output_path}")


def main():
    unreal.log(f"🔍 开始扫描材质: {SCAN_PATH}")
    materials = collect_materials(SCAN_PATH)
    unreal.log(f"📦 找到 {len(materials)} 个材质待处理")

    mapping = {}
    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, orig_path in enumerate(materials):
        dither_path = generate_dither_path(orig_path)
        unreal.log(f"[{i+1}/{len(materials)}] 处理: {orig_path}")

        # 如果 dither 版本已存在，跳过转换但记录映射
        if unreal.EditorAssetLibrary.does_asset_exist(dither_path):
            unreal.log(f"  ⏭️ Dither 版本已存在，跳过: {dither_path}")
            mapping[orig_path] = dither_path
            skip_count += 1
            continue

        try:
            create_dither_material(orig_path, dither_path)
            # 验证是否创建成功
            if unreal.EditorAssetLibrary.does_asset_exist(dither_path):
                mapping[orig_path] = dither_path
                success_count += 1
            else:
                unreal.log_error(f"  ❌ 创建失败: {dither_path}")
                fail_count += 1
        except Exception as e:
            unreal.log_error(f"  ❌ 处理异常: {orig_path} → {e}")
            fail_count += 1

    # 强制保存所有 dither 材质（确保磁盘写入生效）
    unreal.log("💾 正在强制保存所有 Dither 材质...")
    for orig_path, dither_path in mapping.items():
        dither_asset_path = dither_path + "." + dither_path.split("/")[-1]
        asset = unreal.EditorAssetLibrary.load_asset(dither_asset_path)
        if asset:
            unreal.MaterialEditingLibrary.recompile_material(asset)
            unreal.EditorAssetLibrary.save_loaded_asset(asset)

    unreal.log("💾 强制保存完成")

    # 写入映射 MD
    write_mapping_md(mapping, MAPPING_OUTPUT)

    unreal.log(f"\n{'='*50}")
    unreal.log(f"✅ 批量处理完成!")
    unreal.log(f"   成功创建: {success_count}")
    unreal.log(f"   已有跳过: {skip_count}")
    unreal.log(f"   失败: {fail_count}")
    unreal.log(f"   总映射数: {len(mapping)}")


if __name__ == "__main__":
    main()
