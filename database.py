import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class DatabaseManager:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_database()
    
    def init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 创建用户积分表 (支持多群组)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_points (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        # 创建月度积分表 (支持多群组)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monthly_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                year_month TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, guild_id, year_month)
            )
        ''')
        
        # 创建精選记录表 (支持多群组)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS featured_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                featured_by_id INTEGER NOT NULL,
                featured_by_name TEXT NOT NULL,
                featured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT,
                bot_message_id INTEGER,
                UNIQUE(thread_id, author_id)
            )
        ''')
        
        # 添加索引以提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_points_guild ON user_points(guild_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_monthly_points_guild ON monthly_points(guild_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_featured_messages_guild ON featured_messages(guild_id)')
        
        conn.commit()
        conn.close()
    
    def get_user_points(self, user_id: int, guild_id: int) -> int:
        """获取用户在指定群组的积分"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('SELECT points FROM user_points WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        result = cursor.fetchone()
        
        conn.close()
        return result[0] if result else 0
    
    def add_user_points(self, user_id: int, username: str, points: int, guild_id: int) -> int:
        """给用户在指定群组添加积分"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 检查用户是否存在
        cursor.execute('SELECT points FROM user_points WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        result = cursor.fetchone()
        
        if result:
            # 用户存在，更新积分
            new_points = result[0] + points
            cursor.execute('''
                UPDATE user_points 
                SET points = ?, username = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ? AND guild_id = ?
            ''', (new_points, username, user_id, guild_id))
        else:
            # 用户不存在，创建新记录
            new_points = points
            cursor.execute('''
                INSERT INTO user_points (user_id, guild_id, username, points)
                VALUES (?, ?, ?, ?)
            ''', (user_id, guild_id, username, new_points))
        
        conn.commit()
        conn.close()
        return new_points
    
    def is_already_featured(self, thread_id: int, author_id: int) -> bool:
        """检查用户在指定帖子中是否已经被精選过"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 1 FROM featured_messages 
            WHERE thread_id = ? AND author_id = ?
        ''', (thread_id, author_id))
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def get_featured_message_by_id(self, message_id: int, thread_id: int) -> Dict:
        """根据留言ID和帖子ID获取精選记录"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT guild_id, author_id, author_name, featured_by_id, featured_by_name, featured_at, bot_message_id
            FROM featured_messages 
            WHERE message_id = ? AND thread_id = ?
        ''', (message_id, thread_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'guild_id': result[0],
                'author_id': result[1],
                'author_name': result[2],
                'featured_by_id': result[3],
                'featured_by_name': result[4],
                'featured_at': result[5],
                'bot_message_id': result[6]
            }
        return None
    
    def remove_featured_message(self, message_id: int, thread_id: int) -> bool:
        """移除精選记录并更新相关积分"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 获取精選记录信息
            featured_info = self.get_featured_message_by_id(message_id, thread_id)
            if not featured_info:
                conn.close()
                return False
            
            # 开始事务
            cursor.execute('BEGIN TRANSACTION')
            
            try:
                # 1. 删除精選记录
                cursor.execute('''
                    DELETE FROM featured_messages 
                    WHERE message_id = ? AND thread_id = ?
                ''', (message_id, thread_id))
                
                # 2. 减少被精選用户的积分
                cursor.execute('''
                    UPDATE user_points 
                    SET points = points - 1, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND guild_id = ?
                ''', (featured_info['author_id'], featured_info['guild_id']))
                
                # 3. 减少被精選用户的月度积分
                year_month = self.get_current_month()
                cursor.execute('''
                    UPDATE monthly_points 
                    SET points = points - 1, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND guild_id = ? AND year_month = ?
                ''', (featured_info['author_id'], featured_info['guild_id'], year_month))
                
                # 提交事务
                cursor.execute('COMMIT')
                conn.close()
                return True
                
            except Exception as e:
                # 回滚事务
                cursor.execute('ROLLBACK')
                conn.close()
                print(f"移除精選记录时发生错误: {e}")
                return False
                
        except Exception as e:
            print(f"移除精選记录时发生错误: {e}")
            return False
    
    def add_featured_message(self, guild_id: int, thread_id: int, message_id: int, 
                           author_id: int, author_name: str,
                           featured_by_id: int, featured_by_name: str, reason: str = None, bot_message_id: int = None) -> bool:
        """添加精選记录"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO featured_messages 
                (guild_id, thread_id, message_id, author_id, author_name, featured_by_id, featured_by_name, reason, bot_message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, thread_id, message_id, author_id, author_name, featured_by_id, featured_by_name, reason, bot_message_id))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # 违反唯一约束，说明已经精選过
            conn.close()
            return False
    
    def get_user_stats(self, user_id: int, guild_id: int) -> Dict:
        """获取用户在指定群组的统计信息"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 获取积分和用户名
        cursor.execute('SELECT points, username FROM user_points WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        points_result = cursor.fetchone()
        points = points_result[0] if points_result else 0
        username = points_result[1] if points_result else None
        
        # 获取被精選次数 (仅限当前群组)
        cursor.execute('''
            SELECT COUNT(*) FROM featured_messages WHERE author_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        featured_count = cursor.fetchone()[0]
        
        # 获取精選他人次数 (仅限当前群组)
        cursor.execute('''
            SELECT COUNT(*) FROM featured_messages WHERE featured_by_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        featuring_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'points': points,
            'username': username,
            'featured_count': featured_count,
            'featuring_count': featuring_count
        }
    
    def get_thread_stats(self, thread_id: int) -> List[Dict]:
        """获取帖子精選统计"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT author_id, author_name, featured_at, featured_by_name
            FROM featured_messages 
            WHERE thread_id = ?
            ORDER BY featured_at DESC
        ''', (thread_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'author_id': row[0],
                'author_name': row[1],
                'featured_at': row[2],
                'featured_by_name': row[3]
            }
            for row in results
        ] 
    
    def get_user_featured_records(self, user_id: int, guild_id: int, page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
        """获取用户在指定群组被精選的记录（分页）"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 获取总记录数
        cursor.execute('''
            SELECT COUNT(*) FROM featured_messages 
            WHERE author_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        total_count = cursor.fetchone()[0]
        
        # 计算偏移量
        offset = (page - 1) * per_page
        
        # 获取分页数据
        cursor.execute('''
            SELECT thread_id, message_id, featured_at, featured_by_name, reason
            FROM featured_messages 
            WHERE author_id = ? AND guild_id = ?
            ORDER BY featured_at DESC
            LIMIT ? OFFSET ?
        ''', (user_id, guild_id, per_page, offset))
        
        results = cursor.fetchall()
        conn.close()
        
        records = [
            {
                'thread_id': row[0],
                'message_id': row[1],
                'featured_at': row[2],
                'featured_by_name': row[3],
                'reason': row[4]
            }
            for row in results
        ]
        
        return records, total_count

    def get_current_month(self) -> str:
        """获取当前年月"""
        return datetime.now().strftime('%Y-%m')
    
    def add_monthly_points(self, user_id: int, username: str, points: int, guild_id: int) -> int:
        """给用户在指定群组添加月度积分"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        year_month = self.get_current_month()
        
        # 检查是否已存在月度积分记录
        cursor.execute('''
            SELECT points FROM monthly_points 
            WHERE user_id = ? AND guild_id = ? AND year_month = ?
        ''', (user_id, guild_id, year_month))
        
        existing = cursor.fetchone()
        
        if existing:
            # 更新现有记录
            new_points = existing[0] + points
            cursor.execute('''
                UPDATE monthly_points 
                SET points = ?, username = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ? AND guild_id = ? AND year_month = ?
            ''', (new_points, username, user_id, guild_id, year_month))
        else:
            # 创建新记录
            new_points = points
            cursor.execute('''
                INSERT INTO monthly_points (user_id, guild_id, username, points, year_month)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, guild_id, username, new_points, year_month))
        
        conn.commit()
        conn.close()
        return new_points
    
    def get_monthly_ranking(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """获取指定群组的月度积分排行榜"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        year_month = self.get_current_month()
        
        cursor.execute('''
            SELECT user_id, username, points
            FROM monthly_points 
            WHERE guild_id = ? AND year_month = ?
            ORDER BY points DESC
            LIMIT ?
        ''', (guild_id, year_month, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'user_id': row[0],
                'username': row[1],
                'points': row[2]
            }
            for row in results
        ]
    
    def get_total_ranking(self, guild_id: int, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """获取指定群组的总积分排行榜（分页）"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 获取总记录数
        cursor.execute('SELECT COUNT(*) FROM user_points WHERE guild_id = ?', (guild_id,))
        total_records = cursor.fetchone()[0]
        
        # 计算总页数
        total_pages = (total_records + per_page - 1) // per_page
        
        # 获取当前页数据
        offset = (page - 1) * per_page
        cursor.execute('''
            SELECT user_id, username, points
            FROM user_points 
            WHERE guild_id = ?
            ORDER BY points DESC
            LIMIT ? OFFSET ?
        ''', (guild_id, per_page, offset))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'user_id': row[0],
                'username': row[1],
                'points': row[2]
            }
            for row in results
        ], total_pages
    
    def get_user_monthly_points(self, user_id: int, guild_id: int) -> int:
        """获取用户在指定群组的月度积分"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        year_month = self.get_current_month()
        
        cursor.execute('''
            SELECT points FROM monthly_points 
            WHERE user_id = ? AND guild_id = ? AND year_month = ?
        ''', (user_id, guild_id, year_month))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else 0
    
    def clear_monthly_points(self, year_month: str = None, guild_id: int = None) -> bool:
        """清除月度积分"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            if year_month is None:
                year_month = self.get_current_month()
            
            if guild_id is None:
                # 清除所有群组的月度积分
                cursor.execute('DELETE FROM monthly_points WHERE year_month = ?', (year_month,))
            else:
                # 清除指定群组的月度积分
                cursor.execute('DELETE FROM monthly_points WHERE year_month = ? AND guild_id = ?', (year_month, guild_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"清除月度积分时发生错误: {e}")
            return False

    def get_message_preview(self, thread_id: int, message_id: int) -> str:
        """获取消息预览（这里返回一个简单的链接）"""
        return f"https://discord.com/channels/@me/{thread_id}/{message_id}" 