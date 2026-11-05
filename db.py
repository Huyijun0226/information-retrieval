import sqlite3
from pathlib import Path
import json

DB_FILE = Path(__file__).resolve().with_name("settings.db")

def init_db():
    """初始化数据库表"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            api_key TEXT,
            base_url TEXT,
            model_name TEXT
        )
    ''')
    
    # 插入默认行（如果不存在）
    cursor.execute('''
        INSERT OR IGNORE INTO ai_settings (id, api_key, base_url, model_name)
        VALUES (1, '', 'https://api.openai.com/v1', 'gpt-3.5-turbo')
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
    
    conn.commit()
    conn.close()

def load_settings():
    """加载配置"""
    if not DB_FILE.exists():
        init_db()
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT api_key, base_url, model_name FROM ai_settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {"api_key": row[0], "base_url": row[1], "model_name": row[2]}
    return {"api_key": "", "base_url": "https://api.openai.com/v1", "model_name": "gpt-3.5-turbo"}

def save_settings(api_key, base_url, model_name):
    """保存配置"""
    if not DB_FILE.exists():
        init_db()
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE ai_settings 
        SET api_key = ?, base_url = ?, model_name = ?
        WHERE id = 1
    ''', (api_key, base_url, model_name))
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
    cursor.execute('SELECT role, content FROM chat_history ORDER BY id ASC')
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

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
