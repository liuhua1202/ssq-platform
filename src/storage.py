"""
数据存储层 - 支持 JSON 和 SQLite
提供统一的数据访问接口，可切换存储后端
"""
import json
import os
import sqlite3
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StorageBackend:
    """存储后端基类"""
    
    def load_history(self) -> List[Dict]:
        """加载历史数据"""
        raise NotImplementedError
    
    def save_history(self, data: List[Dict]) -> None:
        """保存历史数据"""
        raise NotImplementedError
    
    def add_record(self, record: Dict) -> bool:
        """添加单条记录"""
        raise NotImplementedError
    
    def clear_history(self) -> None:
        """清空历史数据"""
        raise NotImplementedError


class JSONStorage(StorageBackend):
    """JSON 文件存储（默认）"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.history_file = os.path.join(data_dir, "history.json")
        os.makedirs(data_dir, exist_ok=True)
    
    def load_history(self) -> List[Dict]:
        """加载历史数据"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data
            except Exception as e:
                logger.error(f"加载 JSON 历史数据失败：{e}")
                return []
        return []
    
    def save_history(self, data: List[Dict]) -> None:
        """保存历史数据"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON 数据已保存：{len(data)} 条")
        except Exception as e:
            logger.error(f"保存 JSON 数据失败：{e}")
    
    def add_record(self, record: Dict) -> bool:
        """添加单条记录"""
        data = self.load_history()
        
        # 检查是否已存在
        for i, existing in enumerate(data):
            if existing.get('issue') == record.get('issue'):
                data[i] = record  # 更新现有记录
                self.save_history(data)
                return True
        
        data.append(record)
        self.save_history(data)
        return True
    
    def clear_history(self) -> None:
        """清空历史数据"""
        self.save_history([])


class SQLiteStorage(StorageBackend):
    """SQLite 数据库存储（可选，适合大数据量）"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.db_file = os.path.join(data_dir, "history.db")
        os.makedirs(data_dir, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        issue TEXT PRIMARY KEY,
                        date TEXT,
                        red_balls TEXT NOT NULL,
                        blue_ball INTEGER NOT NULL,
                        timestamp TEXT
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_issue 
                    ON history(issue)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_date 
                    ON history(date)
                """)
                conn.commit()
            logger.info(f"SQLite 数据库已初始化：{self.db_file}")
        except Exception as e:
            logger.error(f"初始化 SQLite 数据库失败：{e}")
    
    def load_history(self) -> List[Dict]:
        """加载历史数据"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM history ORDER BY issue DESC"
                )
                data = []
                for row in cursor.fetchall():
                    data.append({
                        'issue': row['issue'],
                        'date': row['date'],
                        'red_balls': json.loads(row['red_balls']),
                        'blue_ball': row['blue_ball'],
                        'timestamp': row['timestamp']
                    })
                logger.debug(f"SQLite 加载 {len(data)} 条记录")
                return data
        except Exception as e:
            logger.error(f"加载 SQLite 数据失败：{e}")
            return []
        finally:
            # 确保连接关闭
            try:
                conn.close()
            except:
                pass
    
    def save_history(self, data: List[Dict]) -> None:
        """保存历史数据（全量替换）"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                # 清空旧数据
                conn.execute("DELETE FROM history")
                
                # 插入新数据
                for record in data:
                    conn.execute(
                        """INSERT OR REPLACE INTO history 
                           (issue, date, red_balls, blue_ball, timestamp)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            record.get('issue'),
                            record.get('date'),
                            json.dumps(record.get('red_balls', [])),
                            record.get('blue_ball'),
                            record.get('timestamp')
                        )
                    )
                conn.commit()
                logger.info(f"SQLite 数据已保存：{len(data)} 条")
        except Exception as e:
            logger.error(f"保存 SQLite 数据失败：{e}")
    
    def add_record(self, record: Dict) -> bool:
        """添加单条记录"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO history 
                       (issue, date, red_balls, blue_ball, timestamp)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        record.get('issue'),
                        record.get('date'),
                        json.dumps(record.get('red_balls', [])),
                        record.get('blue_ball'),
                        record.get('timestamp')
                    )
                )
                conn.commit()
                logger.debug(f"SQLite 添加记录：{record.get('issue')}")
                return True
        except Exception as e:
            logger.error(f"添加 SQLite 记录失败：{e}")
            return False
    
    def clear_history(self) -> None:
        """清空历史数据"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute("DELETE FROM history")
                conn.commit()
            logger.info("SQLite 数据已清空")
        except Exception as e:
            logger.error(f"清空 SQLite 数据失败：{e}")


def create_storage(storage_type: str = "json", data_dir: str = "data") -> StorageBackend:
    """
    创建存储后端
    
    Args:
        storage_type: 存储类型 ("json" 或 "sqlite")
        data_dir: 数据目录
    
    Returns:
        存储后端实例
    """
    if storage_type == "sqlite":
        return SQLiteStorage(data_dir)
    else:
        return JSONStorage(data_dir)
