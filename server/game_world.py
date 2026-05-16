class GameWorld:
    """管理所有在线玩家的状态 + 世界快照"""

    def __init__(self):
        self.players = {}       # player_id -> PlayerState dict
        self._next_player_id = 1
        self._prev_positions = {}  # player_id -> {"x","y","z","t"} 上一次位置+时间

    def add_player(self, session, reuse_pid=None) -> int:
        """玩家进入游戏，分配 player_id，返回 id。
        reuse_pid: 断线重连时复用旧的 player_id
        """
        if reuse_pid is not None:
            pid = reuse_pid
        else:
            pid = self._next_player_id
            self._next_player_id += 1
        # 确保 _next_player_id 不会与复用的 pid 冲突
        if pid >= self._next_player_id:
            self._next_player_id = pid + 1

        char_name = "Unknown"
        if session.player_state:
            char_name = session.player_state.get("char_name", "Unknown")

        # 复用断线重连时保存的状态，否则使用默认值
        if session.player_state:
            saved = session.player_state
            self.players[pid] = {
                "player_id": pid,
                "char_name": saved.get("char_name", "Unknown"),
                "location": saved.get("location", {"x": 0, "y": 0, "z": 200}),
                "rotation": saved.get("rotation", {"pitch": 0, "yaw": 0, "roll": 0}),
                "hp": saved.get("hp", 100),
                "move_speed": saved.get("move_speed", 600),
                "is_sprinting": saved.get("is_sprinting", False),
                "is_aiming": saved.get("is_aiming", False),
                "is_reloading": saved.get("is_reloading", False),
                "is_weapon_drawn": saved.get("is_weapon_drawn", False),
                "is_in_air": saved.get("is_in_air", False),
                "vel_x": saved.get("vel_x", 0.0),
                "vel_z": saved.get("vel_z", 0.0),
            }
        else:
            self.players[pid] = {
                "player_id": pid,
                "char_name": "Unknown",
                "location": {"x": 0, "y": 0, "z": 200},
                "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
                "hp": 100,
                "move_speed": 600,
                "is_sprinting": False,
                "is_aiming": False,
                "is_reloading": False,
                "is_weapon_drawn": False,
                "is_in_air": False,
                "vel_x": 0.0,
                "vel_z": 0.0,
            }

        # 更新 session 的 player_state
        if session.player_state is None:
            session.player_state = {}
        session.player_state["player_id"] = pid

        return pid

    def remove_player(self, player_id: int):
        """移除玩家"""
        self.players.pop(player_id, None)
        self._prev_positions.pop(player_id, None)

    def update_player_move(self, player_id, location, rotation, is_sprinting,
                            is_weapon_drawn=False, is_in_air=False):
        """更新玩家位置，并从位置差计算速度"""
        if player_id in self.players:
            p = self.players[player_id]

            # 从位置差计算速度
            import time
            now = time.time()
            prev = self._prev_positions.get(player_id)
            vel_x = 0.0
            vel_z = 0.0
            if prev:
                dt = now - prev["t"]
                if dt > 0.001:  # 避免除零
                    vel_x = (location["x"] - prev["x"]) / dt
                    vel_z = (location["z"] - prev["z"]) / dt
                    # 限幅防止异常值
                    max_vel = 2000.0
                    vel_x = max(-max_vel, min(max_vel, vel_x))
                    vel_z = max(-max_vel, min(max_vel, vel_z))

            self._prev_positions[player_id] = {
                "x": location["x"], "y": location["y"],
                "z": location["z"], "t": now
            }

            p["location"] = location
            p["rotation"] = rotation
            p["is_sprinting"] = is_sprinting
            p["is_weapon_drawn"] = is_weapon_drawn
            p["is_in_air"] = is_in_air
            p["move_speed"] = 900 if is_sprinting else 600
            p["vel_x"] = vel_x
            p["vel_z"] = vel_z

    def update_player_action(self, player_id, action_type):
        """更新玩家动作状态"""
        if player_id not in self.players:
            return
        p = self.players[player_id]
        from proto.tps_pb2 import ActionType
        if action_type == ActionType.ACTION_RELOAD_START:
            p["is_reloading"] = True
        elif action_type == ActionType.ACTION_RELOAD_END:
            p["is_reloading"] = False
        elif action_type == ActionType.ACTION_AIM_START:
            p["is_aiming"] = True
        elif action_type == ActionType.ACTION_AIM_END:
            p["is_aiming"] = False

    def get_player_state(self, player_id: int):
        """获取单个玩家状态"""
        return self.players.get(player_id)

    def get_all_player_states(self) -> list:
        """获取所有玩家状态"""
        return list(self.players.values())

    def get_snapshot(self) -> dict:
        """返回完整世界快照（进入游戏/重连用）"""
        return {
            "players": list(self.players.values()),
        }
