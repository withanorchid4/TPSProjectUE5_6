# 敌人溶解材质设计

## 概述

敌人死亡时，通过替换 mesh slot0 材质为溶解 MID，实现带燃烧边缘的逐步溶解效果。

## 方案选择

**方案 B：通用溶解材质 + MID 动态调参**

- 每个敌人独立 MID 实例，多敌人同时死可各自独立进度
- 使用 `ue.KismetMaterialLibrary.CreateDynamicMaterialInstance()` 创建
- 与 BuffGlow MID 方案技术栈一致

## 材质节点图（M_Dissolve）

**材质属性**：Surface, Blend Mode = Masked（支持 OpacityMask）

### 参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| BaseColor | TextureParameter2D | — | 敌人原始漫反射贴图 |
| Normal | TextureParameter2D | — | 敌人原始法线贴图（可选） |
| DissolveNoise | TextureParameter2D | T_wenli_1 | 噪声图 |
| DissolveAmount | ScalarParameter | 0.0 | 溶解进度 0→1，由 Python 驱动 |
| EdgeColor | VectorParameter | (1,0.3,0) | 燃烧边缘颜色 |
| EdgeWidth | ScalarParameter | 0.05 | 燃烧边缘宽度 |

### 节点逻辑

```
1. DissolveNoise 采样 → 取 R 通道
2. Step(R, DissolveAmount) → DissolveMask (0 或 1)
3. SmoothStep(DissolveAmount - EdgeWidth, DissolveAmount, R) → EdgeMask (0~1 过渡带)
4. EdgeMask - DissolveMask → EdgeBand (只有边缘窄带为非零)
5. BaseColor * DissolveMask → 输出到 BaseColor（溶解区域变黑）
6. EdgeBand * EdgeColor → 输出到 Emissive Color（燃烧边缘发光）
7. DissolveMask → 输出到 OpacityMask（像素裁剪）
```

DissolveAmount 从 0→1 时，噪声图低值区域先被 Step 裁掉 → 按噪声图案逐步溶解。

## Python 驱动逻辑

### 死亡流程

```
当前：死亡 → 死亡动画 → Destroy

新：死亡 → 替换 slot0 为溶解 MID → 死亡动画 → 
     溶解动画(2s) DissolveAmount 0→1 → Destroy
```

### 关键代码

```python
# _on_death 中：
dissolve_mid = ue.KismetMaterialLibrary.CreateDynamicMaterialInstance(
    self, dissolve_mat, "DissolveMID")
dissolve_mid.OwnByPython()
dissolve_mid.SetTextureParameterValue("BaseColor", original_texture)
dissolve_mid.SetScalarParameterValue("DissolveAmount", 0.0)
mesh.SetMaterial(0, dissolve_mid)

# ReceiveTick 中：
if self._dissolve_mid:
    self._dissolve_progress += delta_time / DISSOLVE_DURATION
    self._dissolve_mid.SetScalarParameterValue("DissolveAmount", self._dissolve_progress)
    if self._dissolve_progress >= 1.0:
        self.Destroy()
```

## 资产清单

| 资产 | 路径 | 说明 |
|------|------|------|
| M_Dissolve | `/Game/Materials/Dissolve/M_Dissolve` | 溶解材质（Masked） |
| T_wenli_1 | `/Game/Materials/Dissolve/Texture/T_wenli_1` | 噪声图（已有） |

## 代码修改清单

| 文件 | 修改内容 |
|------|----------|
| `enemy/base_enemy.py` | 新增溶解 MID 创建、DissolveAmount 驱动、死亡流程改造 |
