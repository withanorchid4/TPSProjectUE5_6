"""Quick reconnect test with flush logging"""
import socket, struct, sys, time
sys.path.insert(0, r".")

from proto import tps_pb2
from proto.tps_pb2 import MsgId

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def pack(mid, d):
    h = struct.pack("!H", mid)
    p = h + d
    return struct.pack("!I", len(p)) + p

def recv1(s, t=3):
    s.settimeout(t)
    b = b""
    while len(b) < 4:
        c = s.recv(4 - len(b))
        if not c: return None
        b += c
    ml = struct.unpack("!I", b)[0]
    b = b""
    while len(b) < ml:
        c = s.recv(ml - len(b))
        if not c: return None
        b += c
    return (struct.unpack("!H", b[:2])[0], b[2:])

TS = str(int(time.time()))
ACC = "rt_" + TS
CN = "H_" + TS

log("Phase 1: Register + Login + CreateChar + SelectChar + EnterGame")

s = socket.socket()
s.connect(("127.0.0.1", 9999))
log("1. Connected to server")

m = tps_pb2.CsLogin(account=ACC, password="123", is_register=True)
s.sendall(pack(MsgId.CS_LOGIN, m.SerializeToString()))
log("   Sent CsLogin(register)")
r = recv1(s)
if not r:
    log("FAIL: No response to register"); sys.exit(1)
lr = tps_pb2.ScLoginResult()
lr.ParseFromString(r[1])
log(f"2. Register result: success={lr.success}")
if not lr.success:
    log(f"   msg={lr.msg}"); sys.exit(1)

m = tps_pb2.CsGetCharacters()
s.sendall(pack(MsgId.CS_GET_CHARACTERS, m.SerializeToString()))
log("   Sent CsGetCharacters")
r = recv1(s)
if not r:
    log("FAIL: No response to get_characters"); sys.exit(1)
log(f"3. Got character list, msg_id={r[0]}")

m = tps_pb2.CsCreateCharacter(char_name=CN)
s.sendall(pack(MsgId.CS_CREATE_CHAR, m.SerializeToString()))
log("   Sent CsCreateCharacter")
r = recv1(s)
if not r:
    log("FAIL: No response to create_char"); sys.exit(1)
cr = tps_pb2.ScCreateResult()
cr.ParseFromString(r[1])
log(f"4. Create char: success={cr.success}")
if not cr.success:
    log(f"   msg={cr.msg}"); sys.exit(1)
cid = cr.character.char_id

m = tps_pb2.CsSelectCharacter(char_id=cid)
s.sendall(pack(MsgId.CS_SELECT_CHAR, m.SerializeToString()))
log("   Sent CsSelectCharacter")
r = recv1(s)
if not r:
    log("FAIL: No response to select_char"); sys.exit(1)
log(f"5. Enter game: msg_id={r[0]}")
if r[0] != MsgId.SC_ENTER_GAME:
    log(f"   Expected SC_ENTER_GAME(107), got {r[0]}")
    # drain and try again
    for _ in range(5):
        r2 = recv1(s, 0.5)
        if r2:
            log(f"   extra msg: id={r2[0]}")
            if r2[0] == MsgId.SC_ENTER_GAME:
                r = r2
                break
eg = tps_pb2.ScEnterGame()
eg.ParseFromString(r[1])
log(f"   pid={eg.self_state.player_id} loc=({eg.self_state.location.x:.0f},{eg.self_state.location.y:.0f},{eg.self_state.location.z:.0f})")

# Move to a known position
m = tps_pb2.CsMove()
m.location.x = 500
m.location.y = 600
m.location.z = 100
m.rotation.yaw = 90
m.is_sprinting = True
s.sendall(pack(MsgId.CS_MOVE, m.SerializeToString()))
log("6. Sent CsMove to (500,600,100)")

time.sleep(0.3)
# Read ONE broadcast to confirm move was processed, then move on
s.settimeout(0.5)
try:
    s.recv(4096)
    log("   Got broadcast after move")
except:
    log("   No broadcast (timeout), continuing")

log("")
log("Phase 2: Disconnect")
s.close()
log("7. Socket closed")
time.sleep(0.5)

log("")
log("Phase 3: Reconnect with same account")
s2 = socket.socket()
s2.connect(("127.0.0.1", 9999))
log("8. Reconnected to server")

m = tps_pb2.CsLogin(account=ACC, password="123", is_register=False)
s2.sendall(pack(MsgId.CS_LOGIN, m.SerializeToString()))
log("   Sent CsLogin(login)")
r = recv1(s2)
if not r:
    log("FAIL: No response to login"); sys.exit(1)
lr2 = tps_pb2.ScLoginResult()
lr2.ParseFromString(r[1])
log(f"9. Login: success={lr2.success}")
if not lr2.success:
    log(f"   msg={lr2.msg}"); sys.exit(1)

# Check for ScReconnect
log("   Waiting for ScReconnect...")
r = recv1(s2, 2)
if not r:
    log("FAIL: No response after login (timeout)")
    sys.exit(1)

if r[0] == MsgId.SC_RECONNECT:
    rc = tps_pb2.ScReconnect()
    rc.ParseFromString(r[1])
    log(f"10. *** RECONNECT SUCCESS! ***")
    log(f"    pid={rc.self_state.player_id}")
    log(f"    char_name={rc.self_state.char_name}")
    log(f"    loc=({rc.self_state.location.x:.0f},{rc.self_state.location.y:.0f},{rc.self_state.location.z:.0f})")
    log(f"    yaw={rc.self_state.rotation.yaw:.0f}")
    log(f"    hp={rc.self_state.hp}")
    if rc.self_state.location.x >= 400 and rc.self_state.location.y >= 500:
        log("")
        log("=== POSITION PRESERVED - ALL TESTS PASSED ===")
    else:
        log(f"    WARNING: Position not as expected")
else:
    log(f"10. FAIL: Expected SC_RECONNECT(109), got msg_id={r[0]}")

s2.close()
log("Done!")
