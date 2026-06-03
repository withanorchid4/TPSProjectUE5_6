"""Dither遮挡效果：相机与角色之间有障碍物时，替换障碍物材质为半透明Dither版"""

import ue

# orig材质路径 → dither材质路径 的配置映射（扩充只需加条目）
DITHER_MAT_MAP = {
    # "/Game/Cartoon_City_Free/Materials/M_Color": "/Game/Materials/Dither/M_Color",
    "/Game/LowerSector_Mod/Models/SkyTower/Materials/M_SkyTower": "/Game/LowerSector_Mod/Models/SkyTower/Materials/M_SkyTower_Dither",
    "/Game/LowerSector_Mod/Models/Apartment01/Materials/M_Apartment01": "/Game/LowerSector_Mod/Models/Apartment01/Materials/M_Apartment01_Dither",
    "/Game/LowerSector_Mod/Models/BG_Buildings/Materials/M_BG_Building01": "/Game/LowerSector_Mod/Models/BG_Buildings/Materials/M_BG_Building01_Dither",
    "/Game/LowerSector_Mod/Models/Bot/Materials/M_Bottington": "/Game/LowerSector_Mod/Models/Bot/Materials/M_Bottington_Dither",
    "/Game/LowerSector_Mod/Models/Building01/Materials/M_B01_Corner01": "/Game/LowerSector_Mod/Models/Building01/Materials/M_B01_Corner01_Dither",
    "/Game/LowerSector_Mod/Models/Building01/Materials/M_B01_Mid01": "/Game/LowerSector_Mod/Models/Building01/Materials/M_B01_Mid01_Dither",
    "/Game/LowerSector_Mod/Models/BuildingPaneling01/Materials/M_BuildingPaneling01": "/Game/LowerSector_Mod/Models/BuildingPaneling01/Materials/M_BuildingPaneling01_Dither",
    "/Game/LowerSector_Mod/Models/Cables/Materials/M_CablePower": "/Game/LowerSector_Mod/Models/Cables/Materials/M_CablePower_Dither",
    "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_003": "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_003_Dither",
    "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_004": "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_004_Dither",
    "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_005": "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_005_Dither",
    "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_006": "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_006_Dither",
    "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_007": "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_007_Dither",
    "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_008": "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_008_Dither",
    "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_009": "/Game/LowerSector_Mod/Models/Cables/Materials/M_Material_009_Dither",
    "/Game/LowerSector_Mod/Models/ConcreteWalls/Materials/M_ConcreteWalls01": "/Game/LowerSector_Mod/Models/ConcreteWalls/Materials/M_ConcreteWalls01_Dither",
    "/Game/LowerSector_Mod/Models/Entrance01/Materials/M_Entrance01": "/Game/LowerSector_Mod/Models/Entrance01/Materials/M_Entrance01_Dither",
    "/Game/LowerSector_Mod/Models/Entrance01_Top/Materials/M_EntranceTop01": "/Game/LowerSector_Mod/Models/Entrance01_Top/Materials/M_EntranceTop01_Dither",
    "/Game/LowerSector_Mod/Models/Entrance02/Materials/M_Entrance02": "/Game/LowerSector_Mod/Models/Entrance02/Materials/M_Entrance02_Dither",
    "/Game/LowerSector_Mod/Models/LightProps/Materials/M_Lightpole01": "/Game/LowerSector_Mod/Models/LightProps/Materials/M_Lightpole01_Dither",
    "/Game/LowerSector_Mod/Models/Pipes/Materials/M_Pipes1": "/Game/LowerSector_Mod/Models/Pipes/Materials/M_Pipes1_Dither",
    "/Game/LowerSector_Mod/Models/PowerBox/Materials/M_PowerBox": "/Game/LowerSector_Mod/Models/PowerBox/Materials/M_PowerBox_Dither",
    "/Game/LowerSector_Mod/Models/PowerCar/Materials/M_PowerCar": "/Game/LowerSector_Mod/Models/PowerCar/Materials/M_PowerCar_Dither",
    "/Game/LowerSector_Mod/Models/RollDoor01/Materials/M_RollDoor": "/Game/LowerSector_Mod/Models/RollDoor01/Materials/M_RollDoor_Dither",
    "/Game/LowerSector_Mod/Models/RoofTop/Materials/M_RoofTop": "/Game/LowerSector_Mod/Models/RoofTop/Materials/M_RoofTop_Dither",
    "/Game/LowerSector_Mod/Models/SideWalk/Materials/M_SideWalk": "/Game/LowerSector_Mod/Models/SideWalk/Materials/M_SideWalk_Dither",
    "/Game/LowerSector_Mod/Models/SkyTower/Materials/M_SkyTower": "/Game/LowerSector_Mod/Models/SkyTower/Materials/M_SkyTower_Dither",
    "/Game/LowerSector_Mod/Models/Skybridge/Materials/M_Skybridge": "/Game/LowerSector_Mod/Models/Skybridge/Materials/M_Skybridge_Dither",
    "/Game/LowerSector_Mod/Models/Tower8x/Materials/M_Tower8x": "/Game/LowerSector_Mod/Models/Tower8x/Materials/M_Tower8x_Dither",
    "/Game/LowerSector_Mod/Models/Wall01/Materials/M_Wall01": "/Game/LowerSector_Mod/Models/Wall01/Materials/M_Wall01_Dither",
    "/Game/LowerSector_Mod/Models/Wall6x/Materials/M_Wall6x": "/Game/LowerSector_Mod/Models/Wall6x/Materials/M_Wall6x_Dither",
    "/Game/LowerSector_Mod/Models/Workshop/Materials/M_Workshop": "/Game/LowerSector_Mod/Models/Workshop/Materials/M_Workshop_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Asphalt_Dark_Gray": "/Game/Cartoon_City_Free/Materials/M_Asphalt_Dark_Gray_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Billboard": "/Game/Cartoon_City_Free/Materials/M_Billboard_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Car_Color": "/Game/Cartoon_City_Free/Materials/M_Car_Color_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Car_Headlights": "/Game/Cartoon_City_Free/Materials/M_Car_Headlights_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Car_Taillights": "/Game/Cartoon_City_Free/Materials/M_Car_Taillights_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Color": "/Game/Cartoon_City_Free/Materials/M_Color_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Color_Glossy": "/Game/Cartoon_City_Free/Materials/M_Color_Glossy_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Emissive": "/Game/Cartoon_City_Free/Materials/M_Emissive_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Glass": "/Game/Cartoon_City_Free/Materials/M_Glass_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Graffiti": "/Game/Cartoon_City_Free/Materials/M_Graffiti_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Grass": "/Game/Cartoon_City_Free/Materials/M_Grass_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Metal": "/Game/Cartoon_City_Free/Materials/M_Metal_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Road_Signs": "/Game/Cartoon_City_Free/Materials/M_Road_Signs_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Roads": "/Game/Cartoon_City_Free/Materials/M_Roads_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Scrolling_Text": "/Game/Cartoon_City_Free/Materials/M_Scrolling_Text_Dither",
    "/Game/Cartoon_City_Free/Materials/M_Tile_1": "/Game/Cartoon_City_Free/Materials/M_Tile_1_Dither"
}


class DitherOcclusion:
    """管理相机遮挡时的Dither材质替换与恢复"""

    def __init__(self, owner, camera):
        """
        Args:
            owner: 角色Actor，用作WorldContextObject和射线终点
            camera: CameraComponent实例，提供相机位置
        """
        self._owner = owner
        self._camera = camera
        self._lookup = {}             # {orig_mat_path: (orig_mat, dither_mat, mid_or_None)}
        self._replaced_mats = {}      # {actor: {slot_index: (original_material, mid)}}

    def init(self):
        """预加载Dither材质映射（在ReceiveBeginPlay时调用）"""
        self._lookup = {}
        for orig_path, dither_path in DITHER_MAT_MAP.items():
            orig_name = orig_path.split("/")[-1]
            dither_name = dither_path.split("/")[-1]
            orig_mat = ue.LoadObject(ue.MaterialInterface, f"{orig_path}.{orig_name}")
            dither_mat = ue.LoadObject(ue.MaterialInterface, f"{dither_path}.{dither_name}")
            if orig_mat and dither_mat:
                self._lookup[orig_mat.GetPathName()] = (orig_mat, dither_mat, None)

    def update(self):
        """每帧调用：射线检测遮挡并替换/恢复材质"""
        if not self._camera or not self._camera.camera:
            return
        if not self._lookup:
            return

        cam_loc = self._camera.camera.GetWorldLocation()
        owner_loc = self._owner.GetActorLocation()

        # 头部和腰部两个端点，分别做射线检测
        head_loc = owner_loc + ue.Vector(0, 0, 160.0)
        waist_loc = owner_loc + ue.Vector(0, 0, 90.0)

        hit_actors = set()
        for target_loc in (head_loc, waist_loc):
            trace_start = cam_loc
            ignore_actors = [self._owner]
            for _ in range(10):  # 最多穿透10个遮挡物
                direction = target_loc - trace_start
                distance = ue.KismetMathLibrary.VSize(direction)
                if distance <= 0.0:
                    break

                hit_result = ue.KismetSystemLibrary.LineTraceSingle(
                    self._owner,
                    trace_start,
                    target_loc,
                    ue.ETraceTypeQuery.TraceTypeQuery1,  # Visibility
                    False,  # bTraceComplex
                    ignore_actors,
                    0,      # EDrawDebugTrace::None
                    True,   # bIgnoreSelf
                )

                b_hit, hit_data = hit_result if isinstance(hit_result, tuple) and len(hit_result) == 2 else (False, None)
                if not (b_hit and hit_data and hasattr(hit_data, 'bBlockingHit') and hit_data.bBlockingHit):
                    break

                comp_ptr = hit_data.Component
                hit_actor = None
                if comp_ptr and hasattr(comp_ptr, 'Get'):
                    comp = comp_ptr.Get()
                    if comp and hasattr(comp, 'GetOwner'):
                        hit_actor = comp.GetOwner()

                if hit_actor:
                    hit_actors.add(hit_actor)
                    ignore_actors.append(hit_actor)
                    # 从命中点稍微偏移继续下一次trace
                    trace_start = hit_data.Location + (target_loc - hit_data.Location) * 0.01
                else:
                    break

        # 对命中的actor做替换
        for actor in hit_actors:
            self._apply_dither(actor)

        # 恢复不再被遮挡的actor
        for actor in list(self._replaced_mats.keys()):
            if actor not in hit_actors:
                self._restore_actor(actor)

    def cleanup(self):
        """还原所有替换并清空引用（在ReceiveEndPlay时调用）"""
        self._restore_all()
        self._lookup.clear()

    # ─── 内部方法 ───

    def _apply_dither(self, actor):
        """检查actor各slot，匹配dither映射的材质替换为Dither MID"""
        mesh_comp = actor.GetComponentByClass(ue.StaticMeshComponent)
        if not mesh_comp:
            mesh_comp = actor.GetComponentByClass(ue.SkeletalMeshComponent)
        if not mesh_comp:
            return

        if actor not in self._replaced_mats:
            self._replaced_mats[actor] = {}

        num_mats = mesh_comp.GetNumMaterials()
        for i in range(num_mats):
            if i in self._replaced_mats[actor]:
                continue

            current_mat = mesh_comp.GetMaterial(i)
            if not current_mat:
                continue

            path = current_mat.GetPathName()
            if path not in self._lookup:
                continue

            orig_mat, dither_mat, mid = self._lookup[path]
            if mid is None:
                mid = ue.KismetMaterialLibrary.CreateDynamicMaterialInstance(
                    self._owner, dither_mat, "DitherMID")
                if not mid:
                    continue
                mid.OwnByPython()
                mid.SetScalarParameterValue(ue.Name("FadeOpacity"), 0.2)
                self._lookup[path] = (orig_mat, dither_mat, mid)

            self._replaced_mats[actor][i] = (orig_mat, mid)
            mesh_comp.SetMaterial(i, mid)

    def _restore_actor(self, actor):
        """还原单个actor的所有Dither替换"""
        slots = self._replaced_mats.get(actor)
        if not slots:
            return
        mesh_comp = actor.GetComponentByClass(ue.StaticMeshComponent)
        if not mesh_comp:
            mesh_comp = actor.GetComponentByClass(ue.SkeletalMeshComponent)
        if mesh_comp:
            for slot_idx, (orig_material, _) in slots.items():
                mesh_comp.SetMaterial(slot_idx, orig_material)
        del self._replaced_mats[actor]

    def _restore_all(self):
        """还原所有已替换Dither材质的物体"""
        for actor in list(self._replaced_mats.keys()):
            self._restore_actor(actor)
