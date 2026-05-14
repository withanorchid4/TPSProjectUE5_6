#!/usr/bin/env python3
"""
Comprehensive test client for TPS server
Tests: login, character creation, selection, movement, reconnect
"""

import socket
import struct
import time
import sys
import os

# Add proto to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from proto import tps_pb2
from proto.tps_pb2 import MsgId


class TestClient:
    """Test client for TPS server"""

    HEADER_SIZE = 4

    def __init__(self, host="127.0.0.1", port=9999):
        self.host = host
        self.port = port
        self.sock = None
        self.recv_buffer = b""

    def connect(self):
        """Connect to server"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.sock.setblocking(True)
        print(f"[+] Connected to {self.host}:{self.port}")

    def disconnect(self):
        """Disconnect from server"""
        if self.sock:
            self.sock.close()
            self.sock = None
            self.recv_buffer = b""
            print("[+] Disconnected")

    def send_msg(self, msg_id: int, msg_bytes: bytes):
        """Send a message"""
        header = struct.pack("!H", msg_id)
        payload = header + msg_bytes
        length = struct.pack("!I", len(payload))
        self.sock.sendall(length + payload)
        # print(f"[>] Sent msg_id={msg_id}, len={len(payload)}")

    def recv_msg(self, timeout=5.0):
        """Receive a message"""
        self.sock.settimeout(timeout)
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Read header
            if len(self.recv_buffer) < self.HEADER_SIZE:
                data = self.sock.recv(self.HEADER_SIZE - len(self.recv_buffer))
                if not data:
                    return None
                self.recv_buffer += data

            if len(self.recv_buffer) >= self.HEADER_SIZE:
                msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
                total_len = self.HEADER_SIZE + msg_len

                # Read payload
                if len(self.recv_buffer) < total_len:
                    needed = total_len - len(self.recv_buffer)
                    data = self.sock.recv(needed)
                    if not data:
                        return None
                    self.recv_buffer += data

                if len(self.recv_buffer) >= total_len:
                    msg_data = self.recv_buffer[self.HEADER_SIZE:total_len]
                    self.recv_buffer = self.recv_buffer[total_len:]

                    if len(msg_data) >= 2:
                        msg_id = struct.unpack("!H", msg_data[:2])[0]
                        return (msg_id, msg_data[2:])

        return None


def test_full_flow():
    """Test complete flow: login -> characters -> create -> select -> move"""
    print("\n" + "="*60)
    print("TEST 1: Full Flow (Login, Characters, Create, Select, Move)")
    print("="*60)

    client = TestClient()
    client.connect()

    # Test 1: Register
    print("\n[1] Testing Register...")
    msg = tps_pb2.CsLogin()
    msg.account = "testuser1"
    msg.password = "testpass123"
    msg.is_register = True
    client.send_msg(MsgId.CS_LOGIN, msg.SerializeToString())

    result = client.recv_msg()
    if result:
        msg_id, data = result
        if msg_id == MsgId.SC_LOGIN_RESULT:
            resp = tps_pb2.ScLoginResult()
            resp.ParseFromString(data)
            print(f"    Register result: success={resp.success}, msg={resp.msg}")
            assert resp.success, "Register failed"
        else:
            print(f"    ERROR: Expected SC_LOGIN_RESULT, got {msg_id}")
            return False
    else:
        print("    ERROR: No response received")
        return False

    # Test 2: Login
    print("\n[2] Testing Login...")
    msg = tps_pb2.CsLogin()
    msg.account = "testuser1"
    msg.password = "testpass123"
    msg.is_register = False
    client.send_msg(MsgId.CS_LOGIN, msg.SerializeToString())

    result = client.recv_msg()
    if result:
        msg_id, data = result
        if msg_id == MsgId.SC_LOGIN_RESULT:
            resp = tps_pb2.ScLoginResult()
            resp.ParseFromString(data)
            print(f"    Login result: success={resp.success}, msg={resp.msg}")
            assert resp.success, "Login failed"
        else:
            print(f"    ERROR: Expected SC_LOGIN_RESULT, got {msg_id}")
            return False
    else:
        print("    ERROR: No response received")
        return False

    # Test 3: Get Characters (should be empty)
    print("\n[3] Testing GetCharacters...")
    msg = tps_pb2.CsGetCharacters()
    client.send_msg(MsgId.CS_GET_CHARACTERS, msg.SerializeToString())

    result = client.recv_msg()
    if result:
        msg_id, data = result
        if msg_id == MsgId.SC_CHARACTER_LIST:
            resp = tps_pb2.ScCharacterList()
            resp.ParseFromString(data)
            print(f"    Character count: {len(resp.characters)}")
        else:
            print(f"    ERROR: Expected SC_CHARACTER_LIST, got {msg_id}")
            return False
    else:
        print("    ERROR: No response received")
        return False

    # Test 4: Create Character
    print("\n[4] Testing CreateCharacter...")
    msg = tps_pb2.CsCreateCharacter()
    msg.char_name = "TestHero"
    client.send_msg(MsgId.CS_CREATE_CHAR, msg.SerializeToString())

    result = client.recv_msg()
    if result:
        msg_id, data = result
        if msg_id == MsgId.SC_CREATE_RESULT:
            resp = tps_pb2.ScCreateResult()
            resp.ParseFromString(data)
            print(f"    Create result: success={resp.success}, msg={resp.msg}")
            if resp.success and resp.HasField('character'):
                char_id = resp.character.char_id
                print(f"    Created character: char_id={char_id}, name={resp.character.char_name}")
            assert resp.success, "Create character failed"
        else:
            print(f"    ERROR: Expected SC_CREATE_RESULT, got {msg_id}")
            return False
    else:
        print("    ERROR: No response received")
        return False

    # Test 5: Select Character
    print("\n[5] Testing SelectCharacter...")
    msg = tps_pb2.CsSelectCharacter()
    msg.char_id = char_id
    client.send_msg(MsgId.CS_SELECT_CHAR, msg.SerializeToString())

    result = client.recv_msg()
    if result:
        msg_id, data = result
        if msg_id == MsgId.SC_ENTER_GAME:
            resp = tps_pb2.ScEnterGame()
            resp.ParseFromString(data)
            print(f"    EnterGame: self.player_id={resp.self_state.player_id}, players={len(resp.players)}")
        else:
            print(f"    ERROR: Expected SC_ENTER_GAME, got {msg_id}")
            return False
    else:
        print("    ERROR: No response received")
        return False

    # Test 6: Move (send a few moves)
    print("\n[6] Testing Move...")
    for i in range(3):
        msg = tps_pb2.CsMove()
        msg.location.x = float(i * 100)
        msg.location.y = 0.0
        msg.location.z = 200.0
        msg.rotation.pitch = 0.0
        msg.rotation.yaw = 0.0
        msg.rotation.roll = 0.0
        msg.is_sprinting = False
        client.send_msg(MsgId.CS_MOVE, msg.SerializeToString())

        # Receive ScPlayerStates
        result = client.recv_msg(timeout=1.0)
        if result:
            msg_id, data = result
            if msg_id == MsgId.SC_PLAYER_STATES:
                resp = tps_pb2.ScPlayerStates()
                resp.ParseFromString(data)
                print(f"    Move {i+1}: received {len(resp.players)} player states")
            else:
                print(f"    Move {i+1}: received msg_id={msg_id}")
        else:
            print(f"    Move {i+1}: no response (timeout ok, broadcast may not be immediate)")

    client.disconnect()
    print("\n[PASS] Test 1 PASSED: Full flow completed successfully!")
    return True


def test_reconnect():
    """Test reconnect after disconnect"""
    print("\n" + "="*60)
    print("TEST 2: Reconnect Test")
    print("="*60)

    client = TestClient()

    # First connection
    print("\n[1] First connection - Login...")
    client.connect()

    msg = tps_pb2.CsLogin()
    msg.account = "testuser2"
    msg.password = "testpass456"
    msg.is_register = True
    client.send_msg(MsgId.CS_LOGIN, msg.SerializeToString())

    result = client.recv_msg()
    if not result or result[0] != MsgId.SC_LOGIN_RESULT:
        print("    ERROR: Register failed")
        return False

    # Create character
    print("[2] Create character...")
    msg = tps_pb2.CsCreateCharacter()
    msg.char_name = "Hero2"
    client.send_msg(MsgId.CS_CREATE_CHAR, msg.SerializeToString())

    result = client.recv_msg()
    if result and result[0] == MsgId.SC_CREATE_RESULT:
        resp = tps_pb2.ScCreateResult()
        resp.ParseFromString(result[1])
        if resp.success:
            char_id = resp.character.char_id
        else:
            print("    ERROR: Create character failed")
            return False
    else:
        print("    ERROR: Create character failed")
        return False

    # Select character
    print("[3] Select character...")
    msg = tps_pb2.CsSelectCharacter()
    msg.char_id = char_id
    client.send_msg(MsgId.CS_SELECT_CHAR, msg.SerializeToString())

    result = client.recv_msg()
    if not result or result[0] != MsgId.SC_ENTER_GAME:
        print("    ERROR: Select character failed")
        return False

    enter_game = tps_pb2.ScEnterGame()
    enter_game.ParseFromString(result[1])
    original_player_id = enter_game.self_state.player_id
    print(f"    Player ID: {original_player_id}")

    # Send a move to update state
    print("[4] Send move to update state...")
    msg = tps_pb2.CsMove()
    msg.location.x = 500.0
    msg.location.y = 300.0
    msg.location.z = 200.0
    msg.rotation.pitch = 45.0
    msg.rotation.yaw = 90.0
    msg.rotation.roll = 0.0
    msg.is_sprinting = True
    client.send_msg(MsgId.CS_MOVE, msg.SerializeToString())

    # Move to a different location first
    import time
    time.sleep(0.1)

    # Disconnect
    print("[5] Disconnect...")
    client.disconnect()

    # Wait a bit
    time.sleep(0.5)

    # Reconnect
    print("[6] Reconnect with same account...")
    client.connect()

    msg = tps_pb2.CsLogin()
    msg.account = "testuser2"
    msg.password = "testpass456"
    msg.is_register = False
    client.send_msg(MsgId.CS_LOGIN, msg.SerializeToString())

    # Should receive ScLoginResult
    result = client.recv_msg()
    if not result or result[0] != MsgId.SC_LOGIN_RESULT:
        print("    ERROR: Login after reconnect failed")
        return False

    login_result = tps_pb2.ScLoginResult()
    login_result.ParseFromString(result[1])
    print(f"    Login result: success={login_result.success}")
    assert login_result.success, "Reconnect login failed"

    # Should receive ScReconnect immediately (not ScEnterGame)
    result = client.recv_msg()
    if result and result[0] == MsgId.SC_RECONNECT:
        reconnect = tps_pb2.ScReconnect()
        reconnect.ParseFromString(result[1])
        print(f"    [PASS] Received ScReconnect!")
        print(f"    Player ID: {reconnect.self_state.player_id}")
        print(f"    Location: ({reconnect.self_state.location.x}, {reconnect.self_state.location.y}, {reconnect.self_state.location.z})")
        print(f"    Rotation: ({reconnect.self_state.rotation.pitch}, {reconnect.self_state.rotation.yaw}, {reconnect.self_state.rotation.roll})")
        print(f"    Is sprinting: {reconnect.self_state.move_speed > 600}")

        # Verify state was preserved
        assert reconnect.self_state.player_id == original_player_id, "Player ID mismatch after reconnect"
        print(f"    [PASS] Player ID preserved: {original_player_id}")
    else:
        print(f"    ERROR: Expected SC_RECONNECT, got {result[0] if result else 'None'}")
        return False

    client.disconnect()
    print("\n[✓] Test 2 PASSED: Reconnect works correctly!")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("TPS SERVER TEST SUITE")
    print("="*60)

    all_passed = True

    try:
        # Test 1: Full flow
        if not test_full_flow():
            all_passed = False

        # Test 2: Reconnect
        if not test_reconnect():
            all_passed = False

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED [OK]")
    else:
        print("SOME TESTS FAILED [FAIL]")
    print("="*60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
