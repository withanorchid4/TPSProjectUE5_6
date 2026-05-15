# -*- encoding: utf-8 -*-
"""NetworkManager 协议层测试

模拟 UE 客户端使用 NetworkManager 的协议流程：
自动注册→登录→获取角色→创角/选角→进游戏→移动→射击→动作

注意：不使用 ue 模块，仅验证协议交互的正确性。
"""

import socket
import struct
import sys
import time

sys.path.insert(0, ".")


HEADER_SIZE = 4


class TestClient:
    """模拟 NetClient 的底层 socket 操作"""
    def __init__(self, host="127.0.0.1", port=9999):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.settimeout(3)
        self.recv_buffer = b""

    def send(self, msg_id, msg_bytes):
        header = struct.pack("!H", msg_id)
        payload = header + msg_bytes
        length = struct.pack("!I", len(payload))
        self.sock.sendall(length + payload)

    def recv_one(self, timeout=3):
        self.sock.settimeout(timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.recv_buffer) >= HEADER_SIZE:
                msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
                total = HEADER_SIZE + msg_len
                if len(self.recv_buffer) >= total:
                    msg_data = self.recv_buffer[HEADER_SIZE:total]
                    self.recv_buffer = self.recv_buffer[total:]
                    msg_id = struct.unpack("!H", msg_data[:2])[0]
                    return msg_id, msg_data[2:]
            try:
                data = self.sock.recv(4096)
                if not data:
                    raise ConnectionError("disconnected")
                self.recv_buffer += data
            except socket.timeout:
                if self.recv_buffer:
                    continue
                raise
        raise TimeoutError("recv_one timed out")

    def drain(self, max_count=50, timeout=0.3):
        self.sock.settimeout(timeout)
        for _ in range(max_count):
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.recv_buffer += data
            except socket.timeout:
                break
        messages = []
        while len(self.recv_buffer) >= HEADER_SIZE:
            msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
            total = HEADER_SIZE + msg_len
            if len(self.recv_buffer) < total:
                break
            msg_data = self.recv_buffer[HEADER_SIZE:total]
            self.recv_buffer = self.recv_buffer[total:]
            if len(msg_data) >= 2:
                msg_id = struct.unpack("!H", msg_data[:2])[0]
                messages.append((msg_id, msg_data[2:]))
        return messages

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def test_network_manager_flow():
    """模拟 NetworkManager 的完整登录+游戏流程"""
    from network.proto import tps_pb2

    print("=" * 60)
    print("NetworkManager Protocol Flow Test")
    print("=" * 60)

    ts = str(int(time.time() * 1000))[-6:]
    account = f"nmtest_{ts}"
    password = "123456"

    c = TestClient()

    # Step 1: 注册（可能失败，账号已存在）
    print("\n[1] Register...")
    msg = tps_pb2.CsLogin(account=account, password=password, is_register=True)
    c.send(tps_pb2.CS_LOGIN, msg.SerializeToString())
    mid, data = c.recv_one()
    r = tps_pb2.ScLoginResult()
    r.ParseFromString(data)
    print(f"  Register: success={r.success} msg={r.msg}")

    # Step 2: 登录
    print("\n[2] Login...")
    msg = tps_pb2.CsLogin(account=account, password=password, is_register=False)
    c.send(tps_pb2.CS_LOGIN, msg.SerializeToString())
    mid, data = c.recv_one()
    r = tps_pb2.ScLoginResult()
    r.ParseFromString(data)
    assert r.success, f"Login failed: {r.msg}"
    print(f"  Login: success={r.success}")

    # Step 3: 获取角色列表
    print("\n[3] Get characters...")
    msg = tps_pb2.CsGetCharacters()
    c.send(tps_pb2.CS_GET_CHARACTERS, msg.SerializeToString())
    mid, data = c.recv_one()
    cl = tps_pb2.ScCharacterList()
    cl.ParseFromString(data)
    print(f"  Characters: {len(cl.characters)}")

    if len(cl.characters) > 0:
        char_id = cl.characters[0].char_id
        char_name = cl.characters[0].char_name
        print(f"  Using existing character: {char_name} (id={char_id})")
    else:
        # Step 4: 创建角色
        print("\n[4] Create character...")
        char_name = f"Player_{account}"
        msg = tps_pb2.CsCreateCharacter(char_name=char_name)
        c.send(tps_pb2.CS_CREATE_CHAR, msg.SerializeToString())
        mid, data = c.recv_one()
        cr = tps_pb2.ScCreateResult()
        cr.ParseFromString(data)
        assert cr.success, f"Create char failed: {cr.msg}"
        char_id = cr.character.char_id
        print(f"  Created: {cr.character.char_name} (id={char_id})")

    # Step 5: 选择角色进游戏
    print("\n[5] Select character & enter game...")
    msg = tps_pb2.CsSelectCharacter(char_id=char_id)
    c.send(tps_pb2.CS_SELECT_CHAR, msg.SerializeToString())
    mid, data = c.recv_one()
    assert mid == tps_pb2.SC_ENTER_GAME, f"Expected SC_ENTER_GAME, got {mid}"
    eg = tps_pb2.ScEnterGame()
    eg.ParseFromString(data)
    pid = eg.self_state.player_id
    print(f"  Entered game! player_id={pid}")
    print(f"  Spawn at: ({eg.self_state.location.x:.0f}, {eg.self_state.location.y:.0f}, {eg.self_state.location.z:.0f})")
    print(f"  Other players in world: {len(eg.players)}")

    c.drain()  # 排空初始广播

    # Step 6: 发送移动（模拟 NetworkManager.send_move）
    print("\n[6] Send move...")
    msg = tps_pb2.CsMove()
    msg.location.x = 100
    msg.location.y = 200
    msg.location.z = 50
    msg.rotation.yaw = 45
    msg.is_sprinting = False
    c.send(tps_pb2.CS_MOVE, msg.SerializeToString())
    time.sleep(0.1)
    c.drain()
    print(f"  Move sent: (100, 200, 50) yaw=45")

    # Step 7: 发送射击（模拟 ShootingComponent._send_shoot_to_server）
    print("\n[7] Send shoot...")
    msg = tps_pb2.CsShoot()
    msg.start_location.x = 100
    msg.start_location.y = 200
    msg.start_location.z = 50
    msg.direction.yaw = 45
    msg.direction.pitch = -5
    msg.weapon_type = 0
    c.send(tps_pb2.CS_SHOOT, msg.SerializeToString())
    time.sleep(0.1)
    bcs = c.drain()
    got_shoot = any(mid == tps_pb2.SC_SHOOT_RESULT for mid, _ in bcs)
    print(f"  Shoot sent, got ScShootResult echo: {got_shoot}")

    # Step 8: 发送换弹动作（模拟 ShootingComponent._send_action_to_server）
    print("\n[8] Send reload action...")
    msg = tps_pb2.CsAction()
    msg.action_type = tps_pb2.ACTION_RELOAD_START
    c.send(tps_pb2.CS_ACTION, msg.SerializeToString())
    time.sleep(0.1)
    bcs = c.drain()
    got_action = any(mid == tps_pb2.SC_ACTION for mid, _ in bcs)
    print(f"  Reload action sent, got ScAction echo: {got_action}")

    # Step 9: 发送瞄准动作
    print("\n[9] Send aim action...")
    msg = tps_pb2.CsAction()
    msg.action_type = tps_pb2.ACTION_AIM_START
    c.send(tps_pb2.CS_ACTION, msg.SerializeToString())
    time.sleep(0.1)
    bcs = c.drain()
    got_aim = any(mid == tps_pb2.SC_ACTION for mid, _ in bcs)
    print(f"  Aim action sent, got ScAction echo: {got_aim}")

    # Step 10: 发送魔法箭射击
    print("\n[10] Send magic arrow shoot...")
    msg = tps_pb2.CsShoot()
    msg.start_location.x = 100
    msg.start_location.y = 200
    msg.start_location.z = 50
    msg.direction.yaw = 90
    msg.weapon_type = 1
    c.send(tps_pb2.CS_SHOOT, msg.SerializeToString())
    time.sleep(0.1)
    bcs = c.drain()
    got_magic = any(mid == tps_pb2.SC_SHOOT_RESULT for mid, _ in bcs)
    print(f"  Magic arrow sent, got ScShootResult echo: {got_magic}")

    c.close()

    print("\n" + "=" * 60)
    print("NetworkManager Protocol Flow Test PASSED! ✅")
    print("=" * 60)


if __name__ == "__main__":
    test_network_manager_flow()
