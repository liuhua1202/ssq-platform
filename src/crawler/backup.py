"""
数据备份管理 - 自动备份 + 旧备份清理.

职责:
  - 创建带时间戳的备份文件
  - 自动清理超过 keep_count 的旧备份 (默认保留 5 个)
  - 从最新备份恢复
"""
import json
import os
import shutil
from datetime import datetime
from typing import List, Dict, Optional


class BackupManager:
    """历史数据备份管理器."""

    DEFAULT_KEEP_COUNT = 5

    def __init__(self, data_dir: str, filename: str = 'history.json',
                 keep_count: int = DEFAULT_KEEP_COUNT):
        self.data_dir = os.path.abspath(data_dir)
        self.history_file = os.path.join(self.data_dir, filename)
        self.backup_dir = os.path.join(self.data_dir, 'backup')
        self.keep_count = keep_count

        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self) -> Optional[str]:
        """创建备份文件. 返回备份文件路径, 如果历史文件不存在则返回 None."""
        if not os.path.exists(self.history_file):
            return None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(self.backup_dir, f'history_{timestamp}.json')

        try:
            shutil.copy2(self.history_file, backup_file)
        except Exception:
            return None

        self.cleanup_old_backups()
        return backup_file

    def cleanup_old_backups(self) -> int:
        """清理超过 keep_count 的旧备份, 返回被删除的文件数."""
        if not os.path.exists(self.backup_dir):
            return 0

        backup_files = sorted(
            f for f in os.listdir(self.backup_dir) if f.endswith('.json')
        )

        removed = 0
        while len(backup_files) > self.keep_count:
            oldest = backup_files.pop(0)
            try:
                os.remove(os.path.join(self.backup_dir, oldest))
                removed += 1
            except OSError:
                # 单个文件删除失败不影响其他清理
                pass
        return removed

    def list_backups(self) -> List[Dict]:
        """列出所有备份文件及元数据."""
        if not os.path.exists(self.backup_dir):
            return []

        backups = []
        for f in sorted(os.listdir(self.backup_dir), reverse=True):
            if not f.endswith('.json'):
                continue
            filepath = os.path.join(self.backup_dir, f)
            try:
                stat = os.stat(filepath)
                backups.append({
                    'filename': f,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                })
            except OSError:
                continue
        return backups

    def restore_from_latest(self) -> Optional[List[Dict]]:
        """从最新备份恢复数据. 返回 records 列表, 无备份时返回 None."""
        if not os.path.exists(self.backup_dir):
            return None

        backup_files = [f for f in os.listdir(self.backup_dir) if f.endswith('.json')]
        if not backup_files:
            return None

        latest_backup = max(backup_files)
        backup_path = os.path.join(self.backup_dir, latest_backup)

        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def restore_from_file(self, filename: str) -> Optional[List[Dict]]:
        """从指定备份文件恢复数据."""
        backup_path = os.path.join(self.backup_dir, filename)
        if not os.path.exists(backup_path):
            return None

        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
