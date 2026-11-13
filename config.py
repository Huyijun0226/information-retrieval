import os
from cryptography.fernet import Fernet
from pathlib import Path

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent
KEY_FILE = BASE_DIR / "secret.key"

def get_encryption_key():
    """从本地文件加载密钥，如果不存在则生成一个新密钥"""
    if KEY_FILE.exists():
        with open(KEY_FILE, "rb") as f:
            return f.read()
    else:
        # 生成新密钥
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key

# 导出密钥
ENCRYPTION_KEY = get_encryption_key()
