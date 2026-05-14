"""Minimal reconnect test - quick version"""
import socket, struct, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"C:\Users\zilong.luo\Desktop\netease\NeteaseDocs\nepy_mini_NoSC\nepy_mini\Newbie\server")
from proto import tps_pb2
from proto.tps_pb2 import MsgId

def pack_msg(msg_id, msg_bytes):
    header = struct.pack("!H", msg_id)
    payload = header + msg_bytes
    return struct.pack("!I", len(payload)) + payload

def recv_msg(sock, timeout=3.0):
    sock.settimeout(timeout)
    try:
        buf = b""
        while len(buf) < 4:
            c = sock.recv(4 - len(buf))
            if not c: return None
            buf += c
        msg_len = struct.unpack("!I", buf)[0]
        buf = b""
        while len(buf) < msg_len:
            c = sock.recv(msg_len - len(buf))
            if not c: return None
            buf += c
        if len(buf) >= 2:
            return (struct.unpack("!H", buf[:2])[0], buf[2:])
        return None
    except socket.timeout:
        return None

TS = str(int(time.time()))

# --- Phase 1: Register, login, create char, enter game ---
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("127.0.0.1", 9999))
print("[1] Connected")

msg = tps_pb2.CsLogin(account="rt_"+TS, password="123", is_register=True)
sock.sendall(pack_msg(MsgId.CS_LOGIN, msg.SerializeToString()))
r = recv_msg(sock); assert r and r[0] == MsgId.SC_LOGIN_RESULT
lr = tps_pb2.ScLoginResult(); lr.ParseFromString(r[1])
print(f"[2] Register: {lr.success}"); assert lr.success

msg = tps_pb2.CsGetCharacters()
sock.sendall(pack_msg(MsgId.CS_GET_CHARACTERS, msg.SerializeToString()))
r = recv_msg(sock); print(f"[3] Get chars ok")

msg = tps_pb2.CsCreateCharacter(char_name="H_"+TS)
sock.sendall(pack_msg(MsgId.CS_CREATE_CHAR, msg.SerializeToString()))
r = recv_msg(sock); assert r and r[0] == MsgId.SC_CREATE_RESULT
cr = tps_pb2.ScCreateResult(); cr.ParseFromString(r[1])
print(f"[4] Create char: {cr.success}, id={cr.character.char_id}"); assert cr.success
cid = cr.character.char_id

msg = tps_pb2.CsSelectCharacter(char_id=cid)
sock.sendall(pack_msg(MsgId.CS_SELECT_CHAR, msg.SerializeToString()))
r = recv_msg(sock); assert r and r[0] == MsgId.SC_ENTER_GAME
eg = tps_pb2.ScEnterGame(); eg.ParseFromString(r[1])
pid = eg.self_state.player_id
print(f"[5] Enter game: pid={pid}, loc=({eg.self_state.location.x},{eg.self_state.location.y},{eg.self_state.location.z})")

# Move to a known position
msg = tps_pb2.CsMove()
msg.location.x = 500; msg.location.y = 600; msg.location.z = 100
msg.rotation.yaw = 90; msg.is_sprinting = True
sock.sendall(pack_msg(MsgId.CS_MOVE, msg.SerializeToString()))
time.sleep(0.3)
# Drain broadcasts
sock.settimeout(0.2)
try:
    while True: sock.recv(4096)
except: pass
print("[6] Moved to (500,600,100)")

# --- Phase 2: Disconnect ---
sock.close()
print("[7] Disconnected")
time.sleep(0.5)

# --- Phase 3: Reconnect ---
sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock2.connect(("127.0.0.1", 9999))
print("[8] Reconnected")

msg = tps_pb2.CsLogin(account="rt_"+TS, password="123", is_register=False)
sock2.sendall(pack_msg(MsgId.CS_LOGIN, msg.SerializeToString()))
r = recv_msg(sock2); assert r and r[0] == MsgId.SC_LOGIN_RESULT
lr2 = tps_pb2.ScLoginResult(); lr2.ParseFromString(r[1])
print(f"[9] Login: {lr2.success}"); assert lr2.success

# Check for ScReconnect
r = recv_msg(sock2, timeout=2.0)
if r and r[0] == MsgId.SC_RECONNECT:
    rc = tps_pb2.ScReconnect(); rc.ParseFromString(r[1])
    print(f"[10] *** RECONNECT OK! pid={rc.self_state.player_id} "
          f"loc=({rc.self_state.location.x:.0f},{rc.self_state.location.y:.0f},{rc.self_state.location.z:.0f}) "
          f"yaw={rc.self_state.rotation.yaw:.0f} hp={rc.self_state.hp}")
    if rc.self_state.location.x >= 400 and rc.self_state.location.y >= 500:
        print("\n*** POSITION PRESERVED AFTER RECONNECT - ALL TESTS PASSED! ***")
    else:
        print(f"\nWARNING: Position not preserved: ({rc.self_state.location.x:.0f},{rc.self_state.location.y:.0f})")
else:
    print(f"[FAIL] Expected SC_RECONNECT, got msg_id={r[0] if r else 'None'}")

sock2.close()
