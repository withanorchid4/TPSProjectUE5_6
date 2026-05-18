# 特殊材质效果设计

> 作业要求 P5-16：灵活应用UE的材质系统，编写特殊的材质效果

## 概述

为 TPS 游戏实现两个特殊材质效果：**敌人溶解消散** 和 **Buff 发光描边**。
材质着色逻辑用 UE 材质编辑器（蓝图节点）实现，Python 负责触发时机和参数控制。

---

## 效果一：敌人溶解消散

### 视觉效果
- 敌人死亡后身体逐渐溶解，从脚到头消失
- 溶解边缘有橙红色发光（类似燃烧/能量消散）
- 整个过程约 1.5 秒，完成后 Destroy Actor

### 材质实现（M_Dissolve）

核心节点逻辑：
1. **噪声遮罩**：Simplex/Perlin 噪声纹理 → 世界坐标 Y 轴偏移（实现从下往上溶解）
2. **阈值裁切**：`Step(DissolveProgress, NoiseValue)` → 输出到 OpacityMask
3. **边缘发光**：噪声值在阈值附近 ±EdgeWidth 的区域 → Fresnel → 乘以 EmissiveColor（橙红色）
4. **暴露参数**：
   - `DissolveProgress` (Scalar, 0~1)：0=完整，1=完全消失
   - `EdgeColor` (Vector)：默认 (1, 0.3, 0.05) 橙红色
   - `EdgeWidth` (Scalar)：默认 0.05

### Python 驱动

在 `base_enemy.py` 死亡流程中：
1. `CreateDynamicMaterialInstance(M_Dissolve)` → `SetMaterial(0, MID)`
2. `AddTicker` 逐帧递增 `DissolveProgress`（0 → 1，约 1.5 秒）
3. `DissolveProgress >= 1.0` 时 Destroy Actor

### 关键 API
- `ue.MaterialInstanceDynamic.CreateDynamicMaterialInstance(parent_material)`
- `mid.SetScalarParameterValue(ue.Name("DissolveProgress"), value)`
- `mesh.SetMaterial(slot_index, mid)`

---

## 效果二：Buff 发光描边

### 视觉效果
- 角色获得增益 Buff 时，身体发出金色光晕
- 角色获得减益 Buff 时，身体发出红色光晕
- Buff 消失时光晕渐隐
- 叠加最多 3 层，层数影响发光强度

### 材质实现（M_BuffGlow）

核心节点逻辑：
1. **Fresnel** 节点 → 提取边缘区域（指数由 GlowPower 控制）
2. **颜色混合**：Fresnel × GlowColor × GlowIntensity → 加到 Emissive 通道
3. **叠加方式**：作为 OverlayMaterial 或额外材质 slot 叠加在角色 Mesh 上
4. **暴露参数**：
   - `GlowColor` (Vector)：金色 (1, 0.8, 0.2) / 红色 (1, 0.1, 0.1)
   - `GlowIntensity` (Scalar, 0~5)：0=无发光
   - `GlowPower` (Scalar)：Fresnel 指数，默认 2.0

### Python 驱动

在 `base_character.py` Buff 系统中：
1. 首次获得 Buff 时：`CreateDynamicMaterialInstance(M_BuffGlow)` → `SetOverlayMaterial(MID)` 或额外 slot
2. Buff 变化时：
   - 攻击增 Buff 存在 → `SetVectorParameterValue("GlowColor", 金色)`
   - 攻击减 Buff 存在 → `SetVectorParameterValue("GlowColor", 红色)`
   - `SetScalarParameterValue("GlowIntensity", 层数 * 1.5)`
3. 所有 Buff 消失时 → `SetScalarParameterValue("GlowIntensity", 0.0)`

### 关键 API
- `mid.SetVectorParameterValue(ue.Name("GlowColor"), ue.LinearColor(r, g, b, 1))`
- `mid.SetScalarParameterValue(ue.Name("GlowIntensity"), value)`

---

## 整体数据流

```
游戏事件              Python 控制                      UE 材质
────────────────────────────────────────────────────────────────
敌人死亡  →  CreateDynamicMaterialInstance →  M_Dissolve
             SetScalarParam(DissolveProgress)   噪声遮罩+边缘光
             AddTicker 驱动 0→1

获得Buff  →  CreateDynamicMaterialInstance →  M_BuffGlow
             SetVectorParam(GlowColor)          Fresnel+自发光
             SetScalarParam(GlowIntensity)

失去Buff  →  SetScalarParam(GlowIntensity=0)
```

## 需要创建的资产

| 资产 | 路径 | 类型 |
|------|------|------|
| M_Dissolve | /Game/Materials/M_Dissolve | Material |
| M_BuffGlow | /Game/Materials/M_BuffGlow | Material |

## 需要修改的代码

| 文件 | 改动 |
|------|------|
| base_enemy.py | 死亡时触发溶解效果 |
| base_character.py | Buff 变化时驱动发光参数 |
