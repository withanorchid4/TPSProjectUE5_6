class GameWorld:
    """管理所有在线玩家的状态 + 世界快照"""

    def __init__(self):
        self.players = {}       # player_id -> PlayerState dict
        self._next_player_id = 1

    def add_player(self, session) -> int:
        """玩家进入游戏，分配 player_id，返回 id"""
        pid = self._next_player_id
        self._next_player_id += 1

        char_name = "Unknown"
        if session.player_state:
            char_name = session.player_state.get("char_name", "Unknown")

        self.players[pid] = {
            "player_id": pid,
            "char_name": char_name,
            "location": {"x": 0, "y": 0, "z": 200},
            "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
            "hp": 100,
            "move_speed": 600,
            "is_sprinting": False,
            "is_aiming": False,
            "is_reloading": False,
        }

        # 更新 session 的 player_state
        if session.player_state is None:
            session.player_state = {}
        session.player_state["player_id"] = pid

        return pid

    def remove_player(self, player_id: int):
        """移除玩家"""
        self.players.pop(player_id, None)

    def update_player_move(self, player_id, location, rotation, is_sprinting):
        """更新玩家位置"""
        if player_id in self.players:
            p = self.players[player_id]
            p["location"] = location
            p["rotation"] = rotation
            p["is_sprinting"] = is_sprinting
            p["move_speed"] = 900 if is_sprinting else 600

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
