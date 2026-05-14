from proto import tps_pb2
from proto.tps_pb2 import MsgId


def handle_login(server, session, data):
    """处理登录/注册请求，返回需要广播的消息列表"""
    msg = tps_pb2.CsLogin()
    msg.ParseFromString(data)

    if msg.is_register:
        success = server.db.register(msg.account, msg.password)
    else:
        success = server.db.login(msg.account, msg.password)

    result = tps_pb2.ScLoginResult()
    result.success = success
    if not success:
        if msg.is_register:
            result.msg = "注册失败(账号已存在)"
        else:
            result.msg = "账号或密码错误"

    session.send_msg(MsgId.SC_LOGIN_RESULT, result.SerializeToString())

    broadcasts = []

    if success:
        session.account = msg.account
        session.state = "LOGGED_IN"

        # 检查断线重连
        if msg.account in server.disconnected_sessions:
            saved = server.disconnected_sessions.pop(msg.account)
            del server.disconnect_time[msg.account]

            session.player_state = saved
            session.state = "IN_GAME"

            pid = server.game_world.add_player(session)

            # 发送 ScReconnect
            reconnect = tps_pb2.ScReconnect()
            ps = reconnect.self_state
            ps.player_id = saved.get("player_id", pid)
            ps.char_name = saved.get("char_name", "")
            ps.location.x = saved.get("location", {}).get("x", 0)
            ps.location.y = saved.get("location", {}).get("y", 0)
            ps.location.z = saved.get("location", {}).get("z", 200)
            ps.rotation.pitch = saved.get("rotation", {}).get("pitch", 0)
            ps.rotation.yaw = saved.get("rotation", {}).get("yaw", 0)
            ps.rotation.roll = saved.get("rotation", {}).get("roll", 0)
            ps.hp = saved.get("hp", 100)
            ps.move_speed = saved.get("move_speed", 600)

            # 添加其他玩家
            for p in server.game_world.get_all_player_states():
                if p["player_id"] != ps.player_id:
                    player = reconnect.players.add()
                    player.player_id = p["player_id"]
                    player.char_name = p["char_name"]
                    player.location.x = p["location"]["x"]
                    player.location.y = p["location"]["y"]
                    player.location.z = p["location"]["z"]
                    player.rotation.pitch = p["rotation"]["pitch"]
                    player.rotation.yaw = p["rotation"]["yaw"]
                    player.rotation.roll = p["rotation"]["roll"]
                    player.hp = p["hp"]
                    player.move_speed = p["move_speed"]

            session.send_msg(MsgId.SC_RECONNECT, reconnect.SerializeToString())

            # 广播 ScPlayerJoin
            join_msg = tps_pb2.ScPlayerJoin()
            join_msg.player.player_id = ps.player_id
            join_msg.player.char_name = ps.char_name
            join_msg.player.location.x = ps.location.x
            join_msg.player.location.y = ps.location.y
            join_msg.player.location.z = ps.location.z
            join_msg.player.rotation.pitch = ps.rotation.pitch
            join_msg.player.rotation.yaw = ps.rotation.yaw
            join_msg.player.rotation.roll = ps.rotation.roll
            join_msg.player.hp = ps.hp
            join_msg.player.move_speed = ps.move_speed
            join_msg.player.is_sprinting = False
            join_msg.player.is_aiming = False
            join_msg.player.is_reloading = False

            broadcasts.append((MsgId.SC_PLAYER_JOIN, join_msg.SerializeToString(), session))

    return broadcasts


def handle_get_characters(server, session, data):
    """处理获取角色列表"""
    characters = server.db.get_characters(session.account)

    result = tps_pb2.ScCharacterList()
    for char in characters:
        char_info = result.characters.add()
        char_info.char_id = char["char_id"]
        char_info.char_name = char["char_name"]
        char_info.level = char["level"]

    session.send_msg(MsgId.SC_CHARACTER_LIST, result.SerializeToString())
    return []


def handle_create_character(server, session, data):
    """处理创建角色请求"""
    msg = tps_pb2.CsCreateCharacter()
    msg.ParseFromString(data)

    char = server.db.create_character(session.account, msg.char_name)

    result = tps_pb2.ScCreateResult()
    if char:
        result.success = True
        result.msg = "创建角色成功"
        result.character.char_id = char["char_id"]
        result.character.char_name = char["char_name"]
        result.character.level = char["level"]
    else:
        result.success = False
        result.msg = "创建角色失败(角色名已存在)"

    session.send_msg(MsgId.SC_CREATE_RESULT, result.SerializeToString())
    return []


def handle_select_character(server, session, data):
    """处理选择角色进入游戏"""
    msg = tps_pb2.CsSelectCharacter()
    msg.ParseFromString(data)

    char = server.db.get_character_by_id(msg.char_id)

    if not char:
        result = tps_pb2.ScDisconnect()
        result.reason = "角色不存在"
        session.send_msg(MsgId.SC_DISCONNECT, result.SerializeToString())
        return []

    # 设置玩家状态
    if session.player_state is None:
        session.player_state = {}
    session.player_state.update(char)
    session.state = "IN_GAME"

    # 加入游戏世界
    pid = server.game_world.add_player(session)

    # 发送 ScEnterGame
    enter_game = tps_pb2.ScEnterGame()

    # self_state
    ps = enter_game.self_state
    ps.player_id = pid
    ps.char_name = char["char_name"]
    ps.location.x = 0
    ps.location.y = 0
    ps.location.z = 200
    ps.rotation.pitch = 0
    ps.rotation.yaw = 0
    ps.rotation.roll = 0
    ps.hp = 100
    ps.move_speed = 600
    ps.is_sprinting = False
    ps.is_aiming = False
    ps.is_reloading = False

    # 其他玩家
    for p in server.game_world.get_all_player_states():
        if p["player_id"] != pid:
            player = enter_game.players.add()
            player.player_id = p["player_id"]
            player.char_name = p["char_name"]
            player.location.x = p["location"]["x"]
            player.location.y = p["location"]["y"]
            player.location.z = p["location"]["z"]
            player.rotation.pitch = p["rotation"]["pitch"]
            player.rotation.yaw = p["rotation"]["yaw"]
            player.rotation.roll = p["rotation"]["roll"]
            player.hp = p["hp"]
            player.move_speed = p["move_speed"]

    session.send_msg(MsgId.SC_ENTER_GAME, enter_game.SerializeToString())

    # 广播 ScPlayerJoin
    broadcasts = []
    join_msg = tps_pb2.ScPlayerJoin()
    join_msg.player.player_id = ps.player_id
    join_msg.player.char_name = ps.char_name
    join_msg.player.location.x = ps.location.x
    join_msg.player.location.y = ps.location.y
    join_msg.player.location.z = ps.location.z
    join_msg.player.rotation.pitch = ps.rotation.pitch
    join_msg.player.rotation.yaw = ps.rotation.yaw
    join_msg.player.rotation.roll = ps.rotation.roll
    join_msg.player.hp = ps.hp
    join_msg.player.move_speed = ps.move_speed
    join_msg.player.is_sprinting = False
    join_msg.player.is_aiming = False
    join_msg.player.is_reloading = False

    broadcasts.append((MsgId.SC_PLAYER_JOIN, join_msg.SerializeToString(), session))

    return broadcasts


def handle_reconnect_ack(server, session, data):
    """处理重连确认"""
    # 什么都不做，只是确认客户端已经收到重连消息
    return []


def handle_move(server, session, data):
    """处理玩家移动上报"""
    msg = tps_pb2.CsMove()
    msg.ParseFromString(data)

    if session.player_state:
        pid = session.player_state.get("player_id")
        location = {
            "x": float(msg.location.x),
            "y": float(msg.location.y),
            "z": float(msg.location.z)
        }
        rotation = {
            "pitch": float(msg.rotation.pitch),
            "yaw": float(msg.rotation.yaw),
            "roll": float(msg.rotation.roll)
        }

        server.game_world.update_player_move(
            pid,
            location,
            rotation,
            msg.is_sprinting
        )

    return []


def handle_skill(server, session, data):
    """处理技能释放"""
    msg = tps_pb2.CsSkill()
    msg.ParseFromString(data)

    pid = session.player_state.get("player_id") if session.player_state else 0

    # 广播技能结果
    result = tps_pb2.ScSkillResult()
    result.player_id = pid
    result.skill_id = msg.skill_id

    p = server.game_world.get_player_state(pid)
    if p:
        result.location.x = p["location"]["x"]
        result.location.y = p["location"]["y"]
        result.location.z = p["location"]["z"]

    result.target_location.x = msg.target_location.x
    result.target_location.y = msg.target_location.y
    result.target_location.z = msg.target_location.z

    return [(MsgId.SC_SKILL_RESULT, result.SerializeToString(), session)]


def handle_pickup(server, session, data):
    """处理拾取道具"""
    msg = tps_pb2.CsPickup()
    msg.ParseFromString(data)

    pid = session.player_state.get("player_id") if session.player_state else 0

    # 广播拾取结果
    result = tps_pb2.ScPickupResult()
    result.success = True
    result.player_id = pid
    result.item_uid = msg.item_uid

    return [(MsgId.SC_PICKUP_RESULT, result.SerializeToString(), None)]


def handle_shoot(server, session, data):
    """处理射击"""
    msg = tps_pb2.CsShoot()
    msg.ParseFromString(data)

    pid = session.player_state.get("player_id") if session.player_state else 0

    # 广播射击结果
    result = tps_pb2.ScShootResult()
    result.player_id = pid
    result.start_location.x = msg.start_location.x
    result.start_location.y = msg.start_location.y
    result.start_location.z = msg.start_location.z
    result.direction.pitch = msg.direction.pitch
    result.direction.yaw = msg.direction.yaw
    result.direction.roll = msg.direction.roll
    result.weapon_type = msg.weapon_type

    return [(MsgId.SC_SHOOT_RESULT, result.SerializeToString(), None)]


def handle_enemy_event(server, session, data):
    """处理敌人事件（伤害/击杀/晕眩）— 纯广播转发"""
    msg = tps_pb2.CsEnemyEvent()
    msg.ParseFromString(data)

    pid = session.player_state.get("player_id") if session.player_state else 0

    result = tps_pb2.ScEnemyEvent()
    result.enemy_id = msg.enemy_id
    result.event_type = msg.event_type
    result.value = msg.value
    result.player_id = pid

    return [(MsgId.SC_ENEMY_EVENT, result.SerializeToString(), None)]


def handle_action(server, session, data):
    """处理动作同步（换弹/瞄准）"""
    msg = tps_pb2.CsAction()
    msg.ParseFromString(data)

    pid = session.player_state.get("player_id") if session.player_state else 0

    # 更新 GameWorld 中的动作状态
    server.game_world.update_player_action(pid, msg.action_type)

    # 广播给其他玩家
    result = tps_pb2.ScAction()
    result.player_id = pid
    result.action_type = msg.action_type

    return [(MsgId.SC_ACTION, result.SerializeToString(), session)]


def handle_game_result(server, session, data):
    """处理游戏结果（胜利/失败），胜利时升级"""
    msg = tps_pb2.CsGameResult()
    msg.ParseFromString(data)

    pid = session.player_state.get("player_id") if session.player_state else 0
    account = session.account

    result = tps_pb2.ScGameResult()
    result.player_id = pid
    result.result = msg.result
    result.level = msg.level
    result.level_up = False

    # 胜利时升级
    if msg.result == tps_pb2.GAME_VICTORY and account:
        char_name = session.player_state.get("char_name", "") if session.player_state else ""
        if char_name:
            # 查询当前 level 并 +1
            chars = server.db.get_characters(account)
            for char in chars:
                if char["char_name"] == char_name:
                    new_level = char["level"] + 1
                    server.db.update_character_level(char["char_name"], new_level)
                    result.level_up = True
                    print(f"Player {char_name} leveled up to {new_level}")

    return [(MsgId.SC_GAME_RESULT, result.SerializeToString(), None)]


# 消息分发表
HANDLERS = {
    MsgId.CS_LOGIN: handle_login,
    MsgId.CS_GET_CHARACTERS: handle_get_characters,
    MsgId.CS_CREATE_CHAR: handle_create_character,
    MsgId.CS_SELECT_CHAR: handle_select_character,
    MsgId.CS_RECONNECT_ACK: handle_reconnect_ack,
    MsgId.CS_MOVE: handle_move,
    MsgId.CS_SKILL: handle_skill,
    MsgId.CS_PICKUP: handle_pickup,
    MsgId.CS_SHOOT: handle_shoot,
    MsgId.CS_ENEMY_EVENT: handle_enemy_event,
    MsgId.CS_ACTION: handle_action,
    MsgId.CS_GAME_RESULT: handle_game_result,
}
