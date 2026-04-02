#!/usr/bin/env python3
"""
自动备份用户数据脚本
Auto-backup script for user data

功能:
- 自动将用户数据文件提交到Git
- 在每次反馈操作后自动备份
- 保留历史记录，可随时恢复

使用方法:
1. 手动备份: python backup_user_data.py
2. 自动备份: 在web_server.py中调用 backup_user_data()
"""

import subprocess
import os
import sys
from datetime import datetime

# 用户数据文件列表
USER_DATA_FILES = [
    'cache/user_feedback.json',
    'cache/favorite_papers.json',
    'my_scholars.json',
    'user_profile.json',
    'cache/recommendation_history.json',
]

def is_git_repo():
    """检查是否是Git仓库"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return result.returncode == 0
    except:
        return False

def backup_user_data(message=None):
    """
    备份用户数据到Git

    Args:
        message: 自定义提交消息

    Returns:
        tuple: (success: bool, message: str)
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if not is_git_repo():
        return False, "Not a Git repository. Please run: git init"

    # 生成提交消息
    if message is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = f"[Auto Backup] User data backup at {timestamp}"

    try:
        # 添加用户数据文件
        files_added = []
        for file_path in USER_DATA_FILES:
            full_path = os.path.join(base_dir, file_path)
            if os.path.exists(full_path):
                result = subprocess.run(
                    ['git', 'add', file_path],
                    capture_output=True,
                    text=True,
                    cwd=base_dir
                )
                if result.returncode == 0:
                    files_added.append(file_path)

        if not files_added:
            return True, "No user data files to backup"

        # 检查是否有更改
        result = subprocess.run(
            ['git', 'diff', '--cached', '--quiet'],
            capture_output=True,
            text=True,
            cwd=base_dir
        )

        if result.returncode == 0:
            return True, "No changes to commit"

        # 提交更改
        result = subprocess.run(
            ['git', 'commit', '-m', message],
            capture_output=True,
            text=True,
            cwd=base_dir
        )

        if result.returncode == 0:
            return True, f"Backup successful: {message}"
        else:
            return False, f"Git commit failed: {result.stderr}"

    except Exception as e:
        return False, f"Backup error: {str(e)}"

def get_backup_history(limit=10):
    """
    获取备份历史

    Args:
        limit: 返回的记录数量

    Returns:
        list: 备份记录列表
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if not is_git_repo():
        return []

    try:
        result = subprocess.run(
            ['git', 'log', '--oneline', '-n', str(limit), '--', 'cache/user_feedback.json', 'cache/favorite_papers.json', 'user_profile.json'],
            capture_output=True,
            text=True,
            cwd=base_dir
        )

        if result.returncode == 0:
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
        return []
    except:
        return []

def restore_backup(commit_hash):
    """
    恢复到指定备份

    Args:
        commit_hash: Git commit hash

    Returns:
        tuple: (success: bool, message: str)
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if not is_git_repo():
        return False, "Not a Git repository"

    try:
        # 恢复用户数据文件
        for file_path in USER_DATA_FILES:
            full_path = os.path.join(base_dir, file_path)
            result = subprocess.run(
                ['git', 'checkout', commit_hash, '--', file_path],
                capture_output=True,
                text=True,
                cwd=base_dir
            )

        return True, f"Restored to commit {commit_hash}"
    except Exception as e:
        return False, f"Restore error: {str(e)}"

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'history':
            print("Backup History:")
            for line in get_backup_history(20):
                print(f"  {line}")
        elif sys.argv[1] == 'restore' and len(sys.argv) > 2:
            success, msg = restore_backup(sys.argv[2])
            print(msg)
        else:
            print("Usage:")
            print("  python backup_user_data.py          # Create backup")
            print("  python backup_user_data.py history  # Show backup history")
            print("  python backup_user_data.py restore <commit_hash>  # Restore backup")
    else:
        success, msg = backup_user_data()
        print(msg)
