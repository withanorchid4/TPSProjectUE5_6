import struct
import time


class ClientSession:
    """单个客户端连接的读写缓冲 + 消息解包"""

    HEADER_SIZE = 4  # 4字节大端长度头

    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.recv_buffer = b""
        self.account = None           # 登录后设置
        self.player_state = None      # 进游戏后设置
        self.state = "CONNECTED"      # CONNECTED / LOGGED_IN / IN_GAME
        self.last_active = time.time()  # 上次收到消息的时间

    def try_recv(self) -> bool:
        """尝试从 socket 读取数据到缓冲区。返回 False 表示断线。"""
        try:
            data = self.sock.recv(4096)
            if not data:
                return False
            self.recv_buffer += data
            self.last_active = time.time()
            return True
        except Exception:
            return False

    def extract_messages(self) -> list[tuple[int, bytes]]:
        """从缓冲区提取完整的 protobuf 消息列表 [(msg_id, msg_bytes), ...]"""
        messages = []
        while len(self.recv_buffer) >= self.HEADER_SIZE:
            msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
            total_len = self.HEADER_SIZE + msg_len

            if len(self.recv_buffer) < total_len:
                break  # 数据不完整，等下次

            msg_data = self.recv_buffer[self.HEADER_SIZE:total_len]
            self.recv_buffer = self.recv_buffer[total_len:]

            # msg_data 前2字节 = msg_id，剩余 = protobuf body
            if len(msg_data) >= 2:
                msg_id = struct.unpack("!H", msg_data[:2])[0]
                messages.append((msg_id, msg_data[2:]))

        return messages

    def send_msg(self, msg_id: int, msg_bytes: bytes):
        """打包并发送一条 protobuf 消息"""
        header = struct.pack("!H", msg_id)
        payload = header + msg_bytes
        length = struct.pack("!I", len(payload))
        try:
            self.sock.sendall(length + payload)
        except Exception:
            pass  # 发送失败，等 select 检测断线

    def close(self):
        """关闭 socket 连接"""
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
