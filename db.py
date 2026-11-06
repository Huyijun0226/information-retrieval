import sqlite3
from pathlib import Path
import json
import base64
from cryptography.fernet import Fernet

DB_FILE = Path(__file__).resolve().with_name("settings.db")

# 固定的加密密钥 (在实际生产中应该通过环境变量注入，这里为了简化演示直接使用固定值)
ENCRYPTION_KEY = b'wz9-kE0q3wG-yU6f5W3V_s1s2r1k9tX7yU9zH1c4o0w='
cipher_suite = Fernet(ENCRYPTION_KEY)

def encrypt_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    try:
        return cipher_suite.encrypt(api_key.encode()).decode()
    except Exception:
        return ""

def decrypt_api_key(encrypted_key: str) -> str:
    if not encrypted_key:
        return ""
    try:
        return cipher_suite.decrypt(encrypted_key.encode()).decode()
    except Exception:
        # 如果解密失败（比如原先是明文存储的），则直接返回原文本
        return encrypted_key

def init_db():
    """初始化数据库表"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            api_key TEXT,
            base_url TEXT,
            model_name TEXT,
            password TEXT DEFAULT '123456'
        )
    ''')
    
    # 检查是否有 password 列（向下兼容），需在插入数据前完成
    cursor.execute("PRAGMA table_info(ai_settings)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'password' not in columns:
        cursor.execute("ALTER TABLE ai_settings ADD COLUMN password TEXT DEFAULT '123456'")

    # 插入默认行（如果不存在）
    cursor.execute('''
        INSERT OR IGNORE INTO ai_settings (id, api_key, base_url, model_name, password)
        VALUES (1, '', 'https://api.openai.com/v1', 'gpt-3.5-turbo', '123456')
    ''')

    # 添加缺失的表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommendation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed_keyword TEXT,
            synonyms TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_a TEXT,
            group_b TEXT,
            group_d TEXT,
            dbs TEXT,
            start_year TEXT,
            end_year TEXT,
            results TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS translation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_query TEXT,
            group_a TEXT,
            group_b TEXT,
            group_d TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def load_settings():
    """加载配置"""
    if not DB_FILE.exists():
        init_db()
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT api_key, base_url, model_name, password FROM ai_settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {"api_key": decrypt_api_key(row[0]), "base_url": row[1], "model_name": row[2], "password": row[3]}
    return {"api_key": "", "base_url": "https://api.openai.com/v1", "model_name": "gpt-3.5-turbo", "password": "123456"}

def save_settings(api_key, base_url, model_name):
    """保存配置"""
    if not DB_FILE.exists():
        init_db()
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    encrypted_key = encrypt_api_key(api_key)
    cursor.execute('''
        UPDATE ai_settings 
        SET api_key = ?, base_url = ?, model_name = ?
        WHERE id = 1
    ''', (encrypted_key, base_url, model_name))
    conn.commit()
    conn.close()

def update_password(new_password):
    """更新密码"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE ai_settings SET password = ? WHERE id = 1', (new_password,))
    conn.commit()
    conn.close()

# 模块被导入时自动初始化
init_db()

def add_chat_msg(role, content):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO chat_history (role, content) VALUES (?, ?)', (role, content))
    conn.commit()
    conn.close()

def get_chat_history():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT role, content, timestamp FROM chat_history ORDER BY id ASC')
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]

def clear_chat_history():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM chat_history')
    conn.commit()
    conn.close()

def add_recommendation_history(seed_keyword, synonyms):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    synonyms_str = json.dumps(synonyms, ensure_ascii=False) if isinstance(synonyms, list) else str(synonyms)
    cursor.execute('INSERT INTO recommendation_history (seed_keyword, synonyms) VALUES (?, ?)', (seed_keyword, synonyms_str))
    conn.commit()
    conn.close()

def add_query_history(group_a, group_b, group_d, dbs, start_year, end_year, results):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    dbs_str = json.dumps(dbs, ensure_ascii=False) if isinstance(dbs, list) else str(dbs)
    results_str = json.dumps(results, ensure_ascii=False) if isinstance(results, (dict, list)) else str(results)
    cursor.execute('''
        INSERT INTO query_history (group_a, group_b, group_d, dbs, start_year, end_year, results) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (group_a, group_b, group_d, dbs_str, start_year, end_year, results_str))
    conn.commit()
    conn.close()

def add_translation_history(source_query, group_a, group_b, group_d):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO translation_history (source_query, group_a, group_b, group_d) 
        VALUES (?, ?, ?, ?)
    ''', (source_query, group_a, group_b, group_d))
    conn.commit()
    conn.close()

def get_query_history():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, group_a, group_b, group_d, dbs, start_year, end_year, results, timestamp FROM query_history ORDER BY id DESC LIMIT 1000')
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "group_a": r[1], "group_b": r[2], "group_d": r[3], "dbs": r[4], "start_year": r[5], "end_year": r[6], "results": r[7], "timestamp": r[8]} for r in rows]

def get_translation_history():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, source_query, group_a, group_b, group_d, timestamp FROM translation_history ORDER BY id DESC LIMIT 1000')
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "source_query": r[1], "group_a": r[2], "group_b": r[3], "group_d": r[4], "timestamp": r[5]} for r in rows]

