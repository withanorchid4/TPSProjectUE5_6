# -*- encoding: utf-8 -*-
"""NetworkManager — 游戏网络管理器（单例）

封装 NetClient，提供游戏级的自动登录流程和消息收发接口。
BaseCharacter 通过 NetworkManager 接入网络，无需关心底层协议。

用法:
    from network.network_manager import NetworkManager
    nm = NetworkManager.get_instance()
    nm.connect_and_login()  # 自动连接+登录+创角+进游戏
    nm.send_move(loc, rot, is_sprinting)
    nm.send_shoot(start_loc, direction, weapon_type)
"""

import ue
from network.net_client import NetClient
from network.proto import tps_pb2


class NetworkManager:
    """游戏网络管理器

    状态机: DISCONNECTED → CONNECTING → LOGGING_IN → SELECTING_CHAR → IN_GAME
    """

    # 内部状态
    STATE_DISCONNECTED = 0
    STATE_CONNECTING = 1
    STATE_LOGGING_IN = 2
    STATE_SELECTING_CHAR = 3
    STATE_IN_GAME = 4

    # 移动上报间隔（秒）
    MOVE_SEND_INTERVAL = 0.1  # 10fps

    # 默认连接参数
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 9999
    DEFAULT_ACCOUNT = "netease1"
    DEFAULT_PASSWORD = "123"

    def __init__(self):
        self._client = NetClient()
        self._state = self.STATE_DISCONNECTED
        self._account = self.DEFAULT_ACCOUNT
        self._password = self.DEFAULT_PASSWORD
        self._char_id = None
        self._self_player_id = None
        self._self_location = None   # 服务端记录的自身位置（重连时非None） {"x", "y", "z"}
        self._self_rotation = None   # 服务端记录的自身旋转（重连时非None） {"pitch", "yaw", "roll"}
        self._login_step = None  # "register" / "login" / "get_chars" / "create_char" / "select_char"

        # 自动模式标志：connect_and_login() 使用自动流程，UI 模式逐步调用
        self._auto_mode = True

        # 移动上报节流
        self._last_move_time = 0.0

        # 远程玩家状态缓存 {player_id: {location, rotation, hp, ...}}
        self.remote_players = {}

        # 回调：游戏层可注册
        self.on_enter_game = None       # → callback(player_id)
        self.on_player_states = None    # → callback(states_dict)
        self.on_player_join = None      # → callback(player_state_dict)
        self.on_player_leave = None     # → callback(player_id)
        self.on_shoot_result = None     # → callback(shoot_dict)
        self.on_action = None           # → callback(action_dict)
        self.on_enemy_event = None      # → callback(event_dict)
        self.on_disconnect = None       # → callback()

        # 回调：UI 登录流程（仅 UI 模式使用）
        self.on_login_result = None     # → callback(success: bool, msg: str)
        self.on_register_result = None  # → callback(success: bool, msg: str)
        self.on_character_list = None   # → callback(chars: list[dict])
        self.on_create_result = None    # → callback(success: bool, char_info: dict|None)
        self.on_delete_result = None    # → callback(success: bool, msg: str, char_id: int)

        # 注册 NetClient 回调
        self._client.register_callback(tps_pb2.SC_LOGIN_RESULT, self._on_login_result)
        self._client.register_callback(tps_pb2.SC_CHARACTER_LIST, self._on_character_list)
        self._client.register_callback(tps_pb2.SC_CREATE_RESULT, self._on_create_result)
        self._client.register_callback(tps_pb2.SC_DELETE_RESULT, self._on_delete_result)
        self._client.register_callback(tps_pb2.SC_ENTER_GAME, self._on_enter_game)
        self._client.register_callback(tps_pb2.SC_PLAYER_STATES, self._on_player_states)
        self._client.register_callback(tps_pb2.SC_PLAYER_JOIN, self._on_player_join)
        self._client.register_callback(tps_pb2.SC_PLAYER_LEAVE, self._on_player_leave)
        self._client.register_callback(tps_pb2.SC_SHOOT_RESULT, self._on_shoot_result)
        self._client.register_callback(tps_pb2.SC_ACTION, self._on_action)
        self._client.register_callback(tps_pb2.SC_ENEMY_EVENT, self._on_enemy_event)
        self._client.set_disconnect_callback(self._on_server_disconnect)

    # ─── 单例 ───

    _instance = None

    @staticmethod
    def get_instance():
        if NetworkManager._instance is None:
            NetworkManager._instance = NetworkManager()
        return NetworkManager._instance

    @staticmethod
    def reset_instance():
        """重置单例（用于测试或断线后重建）"""
        if NetworkManager._instance:
            NetworkManager._instance.disconnect()
        NetworkManager._instance = None

    # ─── 公开 API ───

    @property
    def state(self):
        return self._state

    @property
    def self_player_id(self):
        return self._self_player_id

    @property
    def is_in_game(self):
        return self._state == self.STATE_IN_GAME

    @property
    def self_location(self):
        """服务端记录的位置（重连时为断线前位置，正常进游戏为None）"""
        return self._self_location

    @property
    def self_rotation(self):
        """服务端记录的旋转（重连时为断线前旋转，正常进游戏为None）"""
        return self._self_rotation

    def connect(self, host=None, port=None):
        """仅建立 TCP 连接（UI 模式使用）

        连接成功后，UI 可调用 login() 或 register()。
        """
        if self._state != self.STATE_DISCONNECTED:
            ue.LogWarning(f"NetworkManager: Already connecting/connected (state={self._state})")
            return False

        host = host or self.DEFAULT_HOST
        port = port or self.DEFAULT_PORT

        self._auto_mode = False
        self._state = self.STATE_CONNECTING

        if not self._client.connect(host, port):
            self._state = self.STATE_DISCONNECTED
            ue.LogError("NetworkManager: Connect failed")
            return False

        ue.LogWarning(f"NetworkManager: Connected to {host}:{port}")
        return True

    def login(self, account, password):
        """发送登录请求（UI 模式使用，需先 connect）"""
        self._auto_mode = False
        self._account = account
        self._password = password
        self._send_login()

    def register(self, account, password):
        """发送注册请求（UI 模式使用，需先 connect）"""
        self._auto_mode = False
        self._account = account
        self._password = password
        self._send_register()

    def get_characters(self):
        """请求角色列表（UI 模式使用，需先 login）"""
        self._send_get_characters()

    def select_character(self, char_id):
        """选择角色进入游戏（UI 模式使用）"""
        self._send_select_character(char_id)

    def create_character(self, char_name=None):
        """创建角色（UI 模式使用）"""
        name = char_name or f"Player_{self._account}"
        self._login_step = "create_char"
        msg = tps_pb2.CsCreateCharacter(char_name=name)
        self._client.send_msg(tps_pb2.CS_CREATE_CHAR, msg.SerializeToString())
        ue.LogWarning(f"NetworkManager: Creating character '{name}'...")

    def delete_character(self, char_id):
        """删除角色（UI 模式使用）"""
        msg = tps_pb2.CsDeleteCharacter(char_id=char_id)
        self._client.send_msg(tps_pb2.CS_DELETE_CHAR, msg.SerializeToString())
        ue.LogWarning(f"NetworkManager: Deleting character {char_id}...")

    def connect_and_login(self, host=None, port=None, account=None, password=None):
        """连接服务器并自动完成登录→创角→进游戏全流程

        整个流程是异步的（由 NetClient ticker 驱动），调用后立即返回。
        登录完成后会触发 on_enter_game 回调。
        """
        if self._state != self.STATE_DISCONNECTED:
            ue.LogWarning(f"NetworkManager: Already connecting/connected (state={self._state})")
            return

        self._account = account or self.DEFAULT_ACCOUNT
        self._password = password or self.DEFAULT_PASSWORD
        self._char_id = None
        self._self_player_id = None

        host = host or self.DEFAULT_HOST
        port = port or self.DEFAULT_PORT

        self._state = self.STATE_CONNECTING
        self._login_step = "register"

        if not self._client.connect(host, port):
            self._state = self.STATE_DISCONNECTED
            ue.LogError("NetworkManager: Connect failed")
            return

        # 连接成功，发送注册请求（如果账号已存在会失败，再走登录）
        self._send_register()

    def disconnect(self):
        """断开连接"""
        self._client.disconnect()
        self._state = self.STATE_DISCONNECTED
        self._login_step = None

    def send_move(self, location, rotation, is_sprinting=False):
        """发送位置同步（节流：MOVE_SEND_INTERVAL 间隔）"""
        if not self.is_in_game:
            return

        current_time = ue.KismetSystemLibrary.GetGameTimeInSeconds(self) if hasattr(self, 'GetWorld') else 0.0
        # 使用简单计时：由 caller 传入 delta_time 累积
        # 这里用 NetClient 的内部计时
        import time
        now = time.time()
        if now - self._last_move_time < self.MOVE_SEND_INTERVAL:
            return
        self._last_move_time = now

        msg = tps_pb2.CsMove()
        msg.location.x = location.get("x", 0.0) if isinstance(location, dict) else float(location.x)
        msg.location.y = location.get("y", 0.0) if isinstance(location, dict) else float(location.y)
        msg.location.z = location.get("z", 0.0) if isinstance(location, dict) else float(location.z)
        msg.rotation.pitch = rotation.get("pitch", 0.0) if isinstance(rotation, dict) else float(rotation.pitch)
        msg.rotation.yaw = rotation.get("yaw", 0.0) if isinstance(rotation, dict) else float(rotation.yaw)
        msg.rotation.roll = rotation.get("roll", 0.0) if isinstance(rotation, dict) else float(rotation.roll)
        msg.is_sprinting = is_sprinting

        self._client.send_msg(tps_pb2.CS_MOVE, msg.SerializeToString())

    def send_shoot(self, start_location, direction, weapon_type=0):
        """发送射击同步"""
        if not self.is_in_game:
            return

        msg = tps_pb2.CsShoot()
        msg.start_location.x = start_location.get("x", 0.0) if isinstance(start_location, dict) else float(start_location.x)
        msg.start_location.y = start_location.get("y", 0.0) if isinstance(start_location, dict) else float(start_location.y)
        msg.start_location.z = start_location.get("z", 0.0) if isinstance(start_location, dict) else float(start_location.z)
        msg.direction.pitch = direction.get("pitch", 0.0) if isinstance(direction, dict) else float(direction.pitch)
        msg.direction.yaw = direction.get("yaw", 0.0) if isinstance(direction, dict) else float(direction.yaw)
        msg.direction.roll = direction.get("roll", 0.0) if isinstance(direction, dict) else float(direction.roll)
        msg.weapon_type = weapon_type

        self._client.send_msg(tps_pb2.CS_SHOOT, msg.SerializeToString())

    def send_action(self, action_type):
        """发送动作同步（换弹/瞄准）"""
        if not self.is_in_game:
            return

        msg = tps_pb2.CsAction()
        msg.action_type = action_type
        self._client.send_msg(tps_pb2.CS_ACTION, msg.SerializeToString())

    # ─── 登录流程（内部） ───

    def _send_register(self):
        """发送注册请求"""
        self._login_step = "register"
        msg = tps_pb2.CsLogin(account=self._account, password=self._password, is_register=True)
        self._client.send_msg(tps_pb2.CS_LOGIN, msg.SerializeToString())
        ue.LogWarning(f"NetworkManager: Registering as '{self._account}'...")

    def _send_login(self):
        """发送登录请求"""
        self._login_step = "login"
        self._state = self.STATE_LOGGING_IN
        msg = tps_pb2.CsLogin(account=self._account, password=self._password, is_register=False)
        self._client.send_msg(tps_pb2.CS_LOGIN, msg.SerializeToString())
        ue.LogWarning(f"NetworkManager: Logging in as '{self._account}'...")

    def _send_get_characters(self):
        """请求角色列表"""
        self._login_step = "get_chars"
        msg = tps_pb2.CsGetCharacters()
        self._client.send_msg(tps_pb2.CS_GET_CHARACTERS, msg.SerializeToString())

    def _send_create_character(self):
        """发送创角请求"""
        self._login_step = "create_char"
        char_name = f"Player_{self._account}"
        msg = tps_pb2.CsCreateCharacter(char_name=char_name)
        self._client.send_msg(tps_pb2.CS_CREATE_CHAR, msg.SerializeToString())
        ue.LogWarning(f"NetworkManager: Creating character '{char_name}'...")

    def _send_select_character(self, char_id):
        """发送选角请求"""
        self._login_step = "select_char"
        self._state = self.STATE_SELECTING_CHAR
        msg = tps_pb2.CsSelectCharacter(char_id=char_id)
        self._client.send_msg(tps_pb2.CS_SELECT_CHAR, msg.SerializeToString())
        ue.LogWarning(f"NetworkManager: Selecting character {char_id}...")

    # ─── NetClient 回调 ───

    def _on_login_result(self, msg_id, data):
        """处理登录/注册结果"""
        result = tps_pb2.ScLoginResult()
        result.ParseFromString(data)

        if self._login_step == "register":
            if self._auto_mode:
                if result.success:
                    ue.LogWarning("NetworkManager: Register success, now logging in...")
                    self._send_login()
                else:
                    ue.LogWarning(f"NetworkManager: Register failed ({result.msg}), trying login...")
                    self._send_login()
            else:
                # UI 模式：回调通知 UI
                if self.on_register_result:
                    try:
                        self.on_register_result(result.success, result.msg)
                    except Exception as e:
                        ue.LogError(f"NetworkManager: on_register_result callback error: {e}")

        elif self._login_step == "login":
            if self._auto_mode:
                if result.success:
                    ue.LogWarning("NetworkManager: Login success!")
                    self._send_get_characters()
                else:
                    ue.LogError(f"NetworkManager: Login failed: {result.msg}")
                    self._state = self.STATE_DISCONNECTED
            else:
                # UI 模式：回调通知 UI
                if self.on_login_result:
                    try:
                        self.on_login_result(result.success, result.msg)
                    except Exception as e:
                        ue.LogError(f"NetworkManager: on_login_result callback error: {e}")
                if not result.success:
                    self._state = self.STATE_DISCONNECTED

    def _on_character_list(self, msg_id, data):
        """处理角色列表"""
        result = tps_pb2.ScCharacterList()
        result.ParseFromString(data)

        if self._auto_mode:
            if len(result.characters) > 0:
                # 选择第一个角色
                char = result.characters[0]
                self._char_id = char.char_id
                ue.LogWarning(f"NetworkManager: Found character '{char.char_name}' (lv{char.level}), selecting...")
                self._send_select_character(char.char_id)
            else:
                # 没有角色，创建一个
                ue.LogWarning("NetworkManager: No characters, creating one...")
                self._send_create_character()
        else:
            # UI 模式：回调通知 UI，由 UI 决定选角/创角
            chars = []
            for c in result.characters:
                chars.append({
                    "char_id": c.char_id,
                    "char_name": c.char_name,
                    "level": c.level,
                })
            if self.on_character_list:
                try:
                    self.on_character_list(chars)
                except Exception as e:
                    ue.LogError(f"NetworkManager: on_character_list callback error: {e}")

    def _on_create_result(self, msg_id, data):
        """处理创角结果"""
        result = tps_pb2.ScCreateResult()
        result.ParseFromString(data)

        if self._auto_mode:
            if result.success:
                self._char_id = result.character.char_id
                ue.LogWarning(f"NetworkManager: Character '{result.character.char_name}' created, selecting...")
                self._send_select_character(result.character.char_id)
            else:
                ue.LogError(f"NetworkManager: Create character failed: {result.msg}")
                self._state = self.STATE_DISCONNECTED
        else:
            # UI 模式：回调通知 UI
            char_info = None
            if result.success:
                char_info = {
                    "char_id": result.character.char_id,
                    "char_name": result.character.char_name,
                    "level": result.character.level,
                }
            if self.on_create_result:
                try:
                    self.on_create_result(result.success, char_info)
                except Exception as e:
                    ue.LogError(f"NetworkManager: on_create_result callback error: {e}")

    def _on_delete_result(self, msg_id, data):
        """处理删除角色结果"""
        result = tps_pb2.ScDeleteResult()
        result.ParseFromString(data)

        if self.on_delete_result:
            try:
                self.on_delete_result(result.success, result.msg, result.char_id)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_delete_result callback error: {e}")

    def _on_enter_game(self, msg_id, data):
        """处理进入游戏（含断线重连）"""
        result = tps_pb2.ScEnterGame()
        result.ParseFromString(data)

        self._self_player_id = result.self_state.player_id
        self._state = self.STATE_IN_GAME

        # 保存服务端记录的位置（重连时为断线前位置，正常进游戏为默认位置）
        loc = result.self_state.location
        rot = result.self_state.rotation
        # 仅当位置非默认时标记为重连位置（供 BaseCharacter 传送）
        if loc.x != 0 or loc.y != 0 or loc.z != 200:
            self._self_location = {"x": loc.x, "y": loc.y, "z": loc.z}
            self._self_rotation = {"pitch": rot.pitch, "yaw": rot.yaw, "roll": rot.roll}
        else:
            self._self_location = None
            self._self_rotation = None

        # 缓存其他玩家
        self.remote_players.clear()
        for p in result.players:
            self.remote_players[p.player_id] = _player_state_to_dict(p)

        loc_str = f"({loc.x:.0f},{loc.y:.0f},{loc.z:.0f})" if self._self_location else "default"
        ue.LogWarning(f"NetworkManager: Entered game! player_id={self._self_player_id}, "
                      f"location={loc_str}, remote_players={list(self.remote_players.keys())}")

        if self.on_enter_game:
            try:
                self.on_enter_game(self._self_player_id)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_enter_game callback error: {e}")

        # 为已在线的远程玩家触发 on_player_join（让 BaseCharacter spawn 远程玩家 Actor）
        if self.on_player_join:
            for pid, pstate in self.remote_players.items():
                try:
                    self.on_player_join(pstate)
                except Exception as e:
                    ue.LogError(f"NetworkManager: on_player_join (existing) callback error: {e}")

    def _on_player_states(self, msg_id, data):
        """处理玩家状态广播"""
        result = tps_pb2.ScPlayerStates()
        result.ParseFromString(data)

        for p in result.players:
            if p.player_id == self._self_player_id:
                continue  # 跳过自己
            self.remote_players[p.player_id] = _player_state_to_dict(p)

        if self.on_player_states:
            try:
                self.on_player_states(self.remote_players)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_player_states callback error: {e}")

    def _on_player_join(self, msg_id, data):
        """处理玩家加入"""
        result = tps_pb2.ScPlayerJoin()
        result.ParseFromString(data)

        self.remote_players[result.player.player_id] = _player_state_to_dict(result.player)
        ue.LogWarning(f"NetworkManager: Player {result.player.player_id} ({result.player.char_name}) joined")

        if self.on_player_join:
            try:
                self.on_player_join(_player_state_to_dict(result.player))
            except Exception as e:
                ue.LogError(f"NetworkManager: on_player_join callback error: {e}")

    def _on_player_leave(self, msg_id, data):
        """处理玩家离开"""
        result = tps_pb2.ScPlayerLeave()
        result.ParseFromString(data)

        pid = result.player_id
        self.remote_players.pop(pid, None)
        ue.LogWarning(f"NetworkManager: Player {pid} left")

        if self.on_player_leave:
            try:
                self.on_player_leave(pid)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_player_leave callback error: {e}")

    def _on_shoot_result(self, msg_id, data):
        """处理射击结果广播"""
        result = tps_pb2.ScShootResult()
        result.ParseFromString(data)

        # 不处理自己的射击（本地已经处理了）
        if result.player_id == self._self_player_id:
            return

        shoot_dict = {
            "player_id": result.player_id,
            "start_location": {"x": result.start_location.x, "y": result.start_location.y, "z": result.start_location.z},
            "direction": {"pitch": result.direction.pitch, "yaw": result.direction.yaw, "roll": result.direction.roll},
            "weapon_type": result.weapon_type,
        }

        if self.on_shoot_result:
            try:
                self.on_shoot_result(shoot_dict)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_shoot_result callback error: {e}")

    def _on_action(self, msg_id, data):
        """处理动作同步广播"""
        result = tps_pb2.ScAction()
        result.ParseFromString(data)

        if result.player_id == self._self_player_id:
            return

        action_dict = {
            "player_id": result.player_id,
            "action_type": result.action_type,
        }

        if self.on_action:
            try:
                self.on_action(action_dict)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_action callback error: {e}")

    def _on_enemy_event(self, msg_id, data):
        """处理敌人事件广播"""
        result = tps_pb2.ScEnemyEvent()
        result.ParseFromString(data)

        event_dict = {
            "enemy_id": result.enemy_id,
            "event_type": result.event_type,
            "value": result.value,
            "player_id": result.player_id,
        }

        if self.on_enemy_event:
            try:
                self.on_enemy_event(event_dict)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_enemy_event callback error: {e}")

    def _on_server_disconnect(self):
        """服务端断开连接"""
        self._state = self.STATE_DISCONNECTED
        ue.LogWarning("NetworkManager: Disconnected from server")

        if self.on_disconnect:
            try:
                self.on_disconnect()
            except Exception as e:
                ue.LogError(f"NetworkManager: on_disconnect callback error: {e}")


def _player_state_to_dict(ps):
    """PlayerState protobuf → dict"""
    return {
        "player_id": ps.player_id,
        "char_name": ps.char_name,
        "location": {"x": ps.location.x, "y": ps.location.y, "z": ps.location.z},
        "rotation": {"pitch": ps.rotation.pitch, "yaw": ps.rotation.yaw, "roll": ps.rotation.roll},
        "hp": ps.hp,
        "move_speed": ps.move_speed,
        "is_sprinting": ps.is_sprinting,
        "is_aiming": ps.is_aiming,
        "is_reloading": ps.is_reloading,
    }
