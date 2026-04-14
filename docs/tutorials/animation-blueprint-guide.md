# 动画蓝图创建指南

> 目标：实现按下右键进入瞄准动画，松开回到普通状态
> 
> 日期：2026年4月6日

---

## 1. 现有资源

### 可用的动画资源

| 路径 | 说明 |
|-----|------|
| `Content/Characters/Mannequins/Anims/Rifle/` | 持枪动画 |
| `Content/Characters/Mannequins/Anims/Rifle/MM_Rifle_Fire.uasset` | 射击动画 |
| `Content/Characters/Mannequins/Anims/Rifle/MM_Rifle_Equip.uasset` | 装备动画 |
| `Content/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS.uasset` | 瞄准待机 |
| `Content/Characters/Mannequins/Anims/Rifle/Jog/` | 持枪奔跑（8方向） |
| `Content/Characters/Mannequins/Anims/Rifle/Walk/` | 持枪行走（8方向） |

### 现有动画蓝图

- `Content/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed.uasset` - 无武器动画蓝图

### 角色骨架

- `SKM_Manny_Simple` 或 `SK_Mannequin`

---

## 2. 创建动画蓝图

### 步骤 2.1：新建动画蓝图

1. 打开 **内容浏览器**
2. 导航到 `Content/Characters/Mannequins/Anims/Rifle/` 目录
3. **右键** → `Animation` → `Animation Blueprint`
4. 设置：
   - **父类**: `AnimInstance`
   - **目标骨架**: `SKM_Manny_Simple`（或你角色使用的骨骼）
5. 点击 **确定**
6. 命名为 `ABP_Rifle`

### 步骤 2.2：创建变量

1. 双击打开 `ABP_Rifle`
2. 在左侧 **My Blueprint** 面板，点击 **+ 变量**
3. 添加以下变量：

| 变量名 | 类型 | 默认值 | 说明 |
|-------|------|-------|------|
| `bIsAiming` | Boolean | false | 是否正在瞄准 |
| `bIsFiring` | Boolean | false | 是否正在射击 |
| `Speed` | Float | 0.0 | 移动速度 |
| `bIsInAir` | Boolean | false | 是否在空中 |

### 步骤 2.3：创建状态机

1. 切换到 **Anim Graph** 标签页
2. **右键** → 搜索 `Add New State Machine`
3. 命名为 `Locomotion`
4. 从 `Locomotion` 输出引脚连接到 `Final Animation Pose`

### 步骤 2.4：添加状态

1. **双击** `Locomotion` 进入状态机编辑器
2. 从 **Entry** 节点拖出，创建状态：
   - `Idle_Rifle` - 持枪待机
   - `Idle_ADS` - 瞄准待机
3. 后续可添加：
   - `Jog_Rifle` - 持枪奔跑
   - `Jog_ADS` - 瞄准奔跑
   - `Jump_Rifle` - 持枪跳跃

### 步骤 2.5：设置状态动画

**状态 `Idle_Rifle`：**
1. 双击进入状态
2. **右键** → 搜索 `MF_Rifle_Idle_ADS`（或 `MF_Rifle_Jog_Fwd` 选一个待机）
3. 连接到 `Output Pose`

**状态 `Idle_ADS`：**
1. 双击进入状态
2. **右键** → 搜索 `MF_Rifle_Idle_ADS`
3. 连接到 `Output Pose`

### 步骤 2.6：添加过渡

**过渡 1：Idle_Rifle → Idle_ADS**
1. 右键 `Idle_Rifle` → `Add Transition to` → `Idle_ADS`
2. 双击过渡箭头
3. 添加条件：`Get bIsAiming` → 连接到 Result
4. 设置 **Transition Duration**: `0.2` 秒（平滑过渡）

**过渡 2：Idle_ADS → Idle_Rifle**
1. 右键 `Idle_ADS` → `Add Transition to` → `Idle_Rifle`
2. 双击过渡箭头
3. 添加条件：`NOT Get bIsAiming`
4. 设置 **Transition Duration**: `0.2` 秒

---

## 3. 在角色蓝图中使用

### 步骤 3.1：设置动画蓝图

1. 打开 `Content/BluePrint/TPSCharacterBP`
2. 选择角色的 **Mesh** 组件
3. 在右侧 **Details** 面板：
   - 找到 `Animation` 分类
   - **Anim Class** 选择 `ABP_Rifle_C`

### 步骤 3.2：连接瞄准变量

**方法 A：在 Event Graph 中设置**

1. 打开 `TPSCharacterBP` 的 **Event Graph**
2. 找到瞄准输入事件（右键按下/松开）
3. 添加节点：
   ```
   Event Aim Pressed
       → Get Mesh
       → Get Anim Instance
       → Cast to ABP_Rifle
       → Set bIsAiming = True
   
   Event Aim Released
       → Get Mesh
       → Get Anim Instance
       → Cast to ABP_Rifle
       → Set bIsAiming = False
   ```

**方法 B：通过 Python 代码设置（当前使用）**

Python 的 `CameraComponent.set_aiming()` 已经处理瞄准状态，需要在 Python 中调用蓝图的变量：

```python
# 在 camera.py 的 set_aiming() 中添加
anim_instance = self.owner.Mesh.GetAnimInstance()
if anim_instance:
    anim_instance.SetBoolParameter("bIsAiming", is_aiming)
```

---

## 4. 测试步骤

1. **编译并保存** 动画蓝图 `ABP_Rifle`
2. **编译并保存** 角色蓝图 `TPSCharacterBP`
3. 点击 **Play** 运行游戏
4. 按住 **鼠标右键** 观察动画是否切换到瞄准状态
5. 松开右键观察是否恢复

---

## 5. 问题记录

### 问题 1：动画蓝图不生效

**症状：** 角色没有播放新动画

**排查：**
- [ ] 检查 Mesh 的 Anim Class 是否设置为 `ABP_Rifle_C`
- [ ] 检查骨架是否匹配（Animation Blueprint 的骨架要和 Mesh 一致）
- [ ] 检查状态机是否连接到 Final Animation Pose

### 问题 2：变量没有更新

**症状：** 按右键没有反应

**排查：**
- [ ] 检查 Python 代码是否正确调用 `SetBoolParameter`
- [ ] 检查变量名是否一致（区分大小写）
- [ ] 在蓝图 Print String 调试变量值

---

## 6. 后续扩展

### 6.1 添加移动动画

状态机需要根据速度切换：

```
Speed > 0 && !bIsAiming → Jog_Rifle
Speed > 0 && bIsAiming  → Walk_ADS (瞄准时慢走)
Speed == 0 && !bIsAiming → Idle_Rifle
Speed == 0 && bIsAiming  → Idle_ADS
```

### 6.2 添加射击动画

射击使用 **AnimMontage** 叠加播放，不中断移动：

1. 在 Event Graph 中监听射击事件
2. 调用 `Play Anim Montage` → `MM_Rifle_Fire`

### 6.3 添加跳跃动画

需要检测 `bIsInAir`：
- 在 Event Update Animation 中：`Get Movement Component` → `Is Falling`

---

## 7. 参考资源

- [UE5 动画蓝图官方文档](https://docs.unrealengine.com/5.0/en-US/animation-blueprints-in-unreal-engine/)
- 项目内动画资源：`Content/Characters/Mannequins/Anims/Rifle/`
