import sqlite3
import time
import os


class Database:
    """数据库封装类，处理账号和角色数据"""

    def __init__(self, db_path="server/game.db"):
        # 确保目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 支持字典式访问
        self._init_tables()

    def _init_tables(self):
        """初始化数据库表"""
        # 读取并执行 db_init.sql
        script_path = os.path.join(os.path.dirname(__file__), "db_init.sql")
        if os.path.exists(script_path):
            with open(script_path, "r", encoding="utf-8") as f:
                script = f.read()
            self.conn.executescript(script)
        else:
            # 如果文件不存在，直接创建表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account   TEXT PRIMARY KEY,
                    password  TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    char_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    account   TEXT NOT NULL,
                    char_name TEXT NOT NULL UNIQUE,
                    level     INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (account) REFERENCES accounts(account)
                )
            """)
        self.conn.commit()

        # 内建三个账号
        self._insert_builtin_accounts()

    def _insert_builtin_accounts(self):
        """插入内建账号 netease1/2/3，密码 123"""
        builtins = [
            ("netease1", "123"),
            ("netease2", "123"),
            ("netease3", "123"),
        ]
        now = time.time()
        for account, password in builtins:
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO accounts (account, password, created_at) VALUES (?, ?, ?)",
                    (account, password, now)
                )
            except Exception:
                pass
        self.conn.commit()

    def register(self, account: str, password: str) -> bool:
        """注册新账号"""
        try:
            now = time.time()
            self.conn.execute(
                "INSERT INTO accounts (account, password, created_at) VALUES (?, ?, ?)",
                (account, password, now)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # 账号已存在
            return False
        except Exception as e:
            print(f"Database.register error: {e}")
            return False

    def login(self, account: str, password: str) -> bool:
        """验证账号密码"""
        try:
            cursor = self.conn.execute(
                "SELECT password FROM accounts WHERE account = ?",
                (account,)
            )
            row = cursor.fetchone()
            if row and row["password"] == password:
                return True
            return False
        except Exception as e:
            print(f"Database.login error: {e}")
            return False

    def get_characters(self, account: str) -> list[dict]:
        """获取账号的所有角色"""
        try:
            cursor = self.conn.execute(
                "SELECT char_id, char_name, level FROM characters WHERE account = ?",
                (account,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Database.get_characters error: {e}")
            return []

    def create_character(self, account: str, char_name: str) -> dict | None:
        """创建新角色，成功返回角色信息，失败返回 None"""
        try:
            now = time.time()
            cursor = self.conn.execute(
                "INSERT INTO characters (account, char_name, level, created_at) VALUES (?, ?, 1, ?)",
                (account, char_name, now)
            )
            self.conn.commit()

            # 获取刚插入的角色信息
            char_id = cursor.lastrowid
            cursor = self.conn.execute(
                "SELECT char_id, char_name, level FROM characters WHERE char_id = ?",
                (char_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.IntegrityError:
            # 角色名已存在
            return None
        except Exception as e:
            print(f"Database.create_character error: {e}")
            return None

    def get_character_by_id(self, char_id: int) -> dict | None:
        """根据角色ID获取角色信息"""
        try:
            cursor = self.conn.execute(
                "SELECT char_id, char_name, level, account FROM characters WHERE char_id = ?",
                (char_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"Database.get_character_by_id error: {e}")
            return None

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def update_character_level(self, char_name: str, new_level: int) -> bool:
        """更新角色等级"""
        try:
            self.conn.execute(
                "UPDATE characters SET level = ? WHERE char_name = ?",
                (new_level, char_name)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Database.update_character_level error: {e}")
            return False
