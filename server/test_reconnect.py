"""Reconnect integration test

Usage:
1. Start server first: python main.py
2. Run this test: python test_reconnect.py
"""

import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import socket
import struct
import time
import sys

# 添加 proto 路径
sys.path.insert(0, ".")
from proto import tps_pb2
from proto.tps_pb2 import MsgId


def pack_msg(msg_id: int, msg_bytes: bytes) -> bytes:
    """打包: [4字节长度][2字节msg_id][protobuf body]"""
    header = struct.pack("!H", msg_id)
    payload = header + msg_bytes
    length = struct.pack("!I", len(payload))
    return length + payload


def recv_msg(sock, timeout=3.0) -> tuple[int, bytes] | None:
    """接收一条完整消息"""
    sock.settimeout(timeout)
    try:
        # 读长度头
        length_data = b""
        while len(length_data) < 4:
            chunk = sock.recv(4 - len(length_data))
            if not chunk:
                return None
            length_data += chunk

        msg_len = struct.unpack("!I", length_data)[0]

        # 读消息体
        msg_data = b""
        while len(msg_data) < msg_len:
            chunk = sock.recv(msg_len - len(msg_data))
            if not chunk:
                return None
            msg_data += chunk

        if len(msg_data) >= 2:
            msg_id = struct.unpack("!H", msg_data[:2])[0]
            return (msg_id, msg_data[2:])
        return None
    except socket.timeout:
        return None


def recv_all_msgs(sock, timeout=1.0) -> list[tuple[int, bytes]]:
    """接收所有可用消息"""
    msgs = []
    while True:
        msg = recv_msg(sock, timeout=timeout if len(msgs) == 0 else 0.1)
        if msg is None:
            break
        msgs.append(msg)
    return msgs


def test_full_reconnect():
    """测试完整断线重连流程"""

    ACCOUNT = f"recon_test_{int(time.time())}"
    PASSWORD = "123"
    CHAR_NAME = f"Hero_{int(time.time())}"

    print("=" * 60)
    print("Phase 1: Register + Login + CreateChar + EnterGame")
    print("=" * 60)

    # 连接服务端
    sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock1.connect(("127.0.0.1", 9999))
    print("[OK] Connected to server")

    # 注册
    msg = tps_pb2.CsLogin()
    msg.account = ACCOUNT
    msg.password = PASSWORD
    msg.is_register = True
    sock1.sendall(pack_msg(MsgId.CS_LOGIN, msg.SerializeToString()))

    result = recv_msg(sock1)
    assert result is not None, "No response for register"
    msg_id, data = result
    assert msg_id == MsgId.SC_LOGIN_RESULT, f"Expected SC_LOGIN_RESULT, got {msg_id}"
    login_result = tps_pb2.ScLoginResult()
    login_result.ParseFromString(data)
    print(f"[OK] Register: success={login_result.success}, msg={login_result.msg}")
    assert login_result.success, f"Register failed: {login_result.msg}"

    # 获取角色列表
    msg = tps_pb2.CsGetCharacters()
    sock1.sendall(pack_msg(MsgId.CS_GET_CHARACTERS, msg.SerializeToString()))

    result = recv_msg(sock1)
    assert result is not None
    msg_id, data = result
    assert msg_id == MsgId.SC_CHARACTER_LIST
    char_list = tps_pb2.ScCharacterList()
    char_list.ParseFromString(data)
    print(f"[OK] Get characters: {len(char_list.characters)} characters")

    # 创建角色
    msg = tps_pb2.CsCreateCharacter()
    msg.char_name = CHAR_NAME
    sock1.sendall(pack_msg(MsgId.CS_CREATE_CHAR, msg.SerializeToString()))

    result = recv_msg(sock1)
    assert result is not None
    msg_id, data = result
    assert msg_id == MsgId.SC_CREATE_RESULT
    create_result = tps_pb2.ScCreateResult()
    create_result.ParseFromString(data)
    print(f"[OK] Create character: success={create_result.success}, name={create_result.character.char_name if create_result.success else 'N/A'}")
    assert create_result.success, f"Create character failed: {create_result.msg}"

    char_id = create_result.character.char_id

    # 选择角色进入游戏
    msg = tps_pb2.CsSelectCharacter()
    msg.char_id = char_id
    sock1.sendall(pack_msg(MsgId.CS_SELECT_CHAR, msg.SerializeToString()))

    result = recv_msg(sock1)
    assert result is not None
    msg_id, data = result
    assert msg_id == MsgId.SC_ENTER_GAME
    enter_game = tps_pb2.ScEnterGame()
    enter_game.ParseFromString(data)
    print(f"[OK] Enter game: player_id={enter_game.self_state.player_id}, "
          f"loc=({enter_game.self_state.location.x:.0f},{enter_game.self_state.location.y:.0f},{enter_game.self_state.location.z:.0f})")
    original_pid = enter_game.self_state.player_id

    # 发送几次移动
    for i in range(5):
        msg = tps_pb2.CsMove()
        msg.location.x = 100.0 + i * 10
        msg.location.y = 200.0 + i * 10
        msg.location.z = 300.0
        msg.rotation.yaw = 45.0 + i * 5
        msg.is_sprinting = False
        sock1.sendall(pack_msg(MsgId.CS_MOVE, msg.SerializeToString()))
        time.sleep(0.05)

    # 等待服务端处理移动
    time.sleep(0.2)
    # 清空广播消息
    recv_all_msgs(sock1, timeout=0.3)

    print(f"\n[OK] Moved to (140, 240, 300)")

    print("\n" + "=" * 60)
    print("Phase 2: Disconnect")
    print("=" * 60)

    # 模拟断线（直接关闭 socket）
    sock1.close()
    print("[OK] Socket closed (simulating disconnect)")

    # 等待服务端检测断线
    time.sleep(0.5)

    print("\n" + "=" * 60)
    print("Phase 3: Reconnect (should trigger ScReconnect)")
    print("=" * 60)

    # 重新连接
    sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock2.connect(("127.0.0.1", 9999))
    print("[OK] Reconnected to server")

    # 用同一账号登录
    msg = tps_pb2.CsLogin()
    msg.account = ACCOUNT
    msg.password = PASSWORD
    msg.is_register = False
    sock2.sendall(pack_msg(MsgId.CS_LOGIN, msg.SerializeToString()))

    result = recv_msg(sock2)
    assert result is not None, "No response for login"
    msg_id, data = result
    assert msg_id == MsgId.SC_LOGIN_RESULT
    login_result = tps_pb2.ScLoginResult()
    login_result.ParseFromString(data)
    print(f"[OK] Login: success={login_result.success}")
    assert login_result.success, f"Login failed: {login_result.msg}"

    # 检查是否收到 ScReconnect
    result = recv_msg(sock2, timeout=2.0)
    assert result is not None, "Expected ScReconnect but got no message!"

    msg_id, data = result
    if msg_id == MsgId.SC_RECONNECT:
        reconnect = tps_pb2.ScReconnect()
        reconnect.ParseFromString(data)
        print(f"[OK] *** RECONNECT SUCCESS! ***")
        print(f"     player_id={reconnect.self_state.player_id}")
        print(f"     char_name={reconnect.self_state.char_name}")
        print(f"     location=({reconnect.self_state.location.x:.0f}, "
              f"{reconnect.self_state.location.y:.0f}, "
              f"{reconnect.self_state.location.z:.0f})")
        print(f"     rotation yaw={reconnect.self_state.rotation.yaw:.0f}")
        print(f"     hp={reconnect.self_state.hp}")

        # 验证位置已恢复（应该是最后一次 CsMove 的位置）
        assert reconnect.self_state.location.x >= 100, \
            f"Expected x>=100, got {reconnect.self_state.location.x}"
        assert reconnect.self_state.location.y >= 200, \
            f"Expected y>=200, got {reconnect.self_state.location.y}"
        print(f"\n[OK] Location preserved after reconnect!")
    else:
        print(f"[FAIL] Expected SC_RECONNECT (109), got msg_id={msg_id}")
        sys.exit(1)

    # 清理
    sock2.close()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_full_reconnect()
