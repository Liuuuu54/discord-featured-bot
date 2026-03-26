import sqlite3
import json
import re
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_featured_messages_guild ON featured_messages(guild_id)')

        # 用户书单主表（每个用户固定 10 张，list_id: 0~9）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_booklists (
                user_id INTEGER NOT NULL,
                list_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, list_id)
            )
        ''')

        # 书单帖子明细（每张书单最多 20 条由业务层控制）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_booklist_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                list_id INTEGER NOT NULL,
                thread_guild_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL,
                thread_title TEXT NOT NULL,
                thread_url TEXT NOT NULL,
                review TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id, list_id) REFERENCES user_booklists(user_id, list_id),
                UNIQUE(user_id, list_id, thread_id)
            )
        ''')

        # 公开书单消息记录
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS public_booklists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                list_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                intro TEXT NOT NULL,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                removed_at TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_booklists_user ON user_booklists(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_booklist_entries_user_list ON user_booklist_entries(user_id, list_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_public_booklists_user_active ON public_booklists(user_id, is_active)')

        # 用户在指定群组的书单帖跳转链接（用于精選紀錄公开面板）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_booklist_thread_links (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                thread_url TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        # 书单帖白名单（每个群组可指定一个论坛频道）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS booklist_thread_whitelist (
                guild_id INTEGER PRIMARY KEY,
                forum_channel_id INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 公开书单最小索引（不存快照，仅用于重启恢复分页按钮）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS public_booklist_indexes (
                message_id INTEGER PRIMARY KEY,
                publisher_user_id INTEGER NOT NULL,
                list_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_public_booklist_indexes_active ON public_booklist_indexes(is_active)')
        
        conn.commit()
        conn.close()
    
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
        """移除精選记录并清理相关数据"""
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
    
    def get_user_stats(self, user_id: int, guild_id: int, include_all_guilds: bool = False) -> Dict:
        """获取用户统计信息（默认指定群组，可选跨群组汇总）"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        if include_all_guilds:
            # 获取用户名（跨群组）
            cursor.execute('SELECT author_name FROM featured_messages WHERE author_id = ? LIMIT 1', (user_id,))
            name_result = cursor.fetchone()
            if not name_result:
                cursor.execute('SELECT featured_by_name FROM featured_messages WHERE featured_by_id = ? LIMIT 1', (user_id,))
                name_result = cursor.fetchone()
        else:
            # 获取用户名（仅当前群组）
            cursor.execute('SELECT author_name FROM featured_messages WHERE author_id = ? AND guild_id = ? LIMIT 1', (user_id, guild_id))
            name_result = cursor.fetchone()
            if not name_result:
                cursor.execute('SELECT featured_by_name FROM featured_messages WHERE featured_by_id = ? AND guild_id = ? LIMIT 1', (user_id, guild_id))
                name_result = cursor.fetchone()
        
        username = name_result[0] if name_result else f"用户{user_id}"

        if include_all_guilds:
            # 获取被精選次数（跨群组）
            cursor.execute('''
                SELECT COUNT(*) FROM featured_messages WHERE author_id = ?
            ''', (user_id,))
            featured_count = cursor.fetchone()[0]

            # 获取引荐人数（跨群组去重统计，按用户ID去重）
            cursor.execute('''
                SELECT COUNT(DISTINCT author_id) FROM featured_messages WHERE featured_by_id = ?
            ''', (user_id,))
            featuring_count = cursor.fetchone()[0]
        else:
            # 获取被精選次数（仅当前群组）
            cursor.execute('''
                SELECT COUNT(*) FROM featured_messages WHERE author_id = ? AND guild_id = ?
            ''', (user_id, guild_id))
            featured_count = cursor.fetchone()[0]

            # 获取引荐人数（仅当前群组，去重统计）
            cursor.execute('''
                SELECT COUNT(DISTINCT author_id) FROM featured_messages WHERE featured_by_id = ? AND guild_id = ?
            ''', (user_id, guild_id))
            featuring_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'username': username,
            'featured_count': featured_count,
            'featuring_count': featuring_count
        }
    
    def get_thread_stats(self, thread_id: int) -> List[Dict]:
        """获取帖子精選统计"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT author_id, author_name, featured_at, featured_by_name, message_id
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
                'featured_by_name': row[3],
                'message_id': row[4]
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
        
        # 計算總頁數
        total_pages = (total_count + per_page - 1) // per_page
        
        return records, total_pages

    def get_user_referral_records(self, user_id: int, guild_id: int, page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
        """获取用户在指定群组精選別人的记录（分页）"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 获取总记录数
        cursor.execute('''
            SELECT COUNT(*) FROM featured_messages 
            WHERE featured_by_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        total_count = cursor.fetchone()[0]
        
        # 计算偏移量
        offset = (page - 1) * per_page
        
        # 获取分页数据
        cursor.execute('''
            SELECT thread_id, message_id, featured_at, author_name, reason
            FROM featured_messages 
            WHERE featured_by_id = ? AND guild_id = ?
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
                'author_name': row[3],
                'reason': row[4]
            }
            for row in results
        ]
        
        # 計算總頁數
        total_pages = (total_count + per_page - 1) // per_page
        
        return records, total_pages



    def get_message_preview(self, thread_id: int, message_id: int) -> str:
        """获取消息预览（这里返回一个简单的链接）"""
        return f"https://discord.com/channels/@me/{thread_id}/{message_id}" 

 

    def get_referral_ranking(self, guild_id: int, page: int = 1, per_page: int = 20, start_date: str = None, end_date: str = None) -> Tuple[List[Dict], int]:
        """获取指定群组的引荐人数排行榜（分页，支持时间范围）"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 构建查询条件
        where_conditions = ["guild_id = ?"]
        params = [guild_id]
        
        if start_date:
            where_conditions.append("featured_at >= ?")
            params.append(start_date)
        
        if end_date:
            where_conditions.append("featured_at <= ?")
            params.append(end_date)
        
        where_clause = " AND ".join(where_conditions)
        
        # 获取总记录数（有引荐记录的用户数量）
        cursor.execute(f'''
            SELECT COUNT(DISTINCT featured_by_id) 
            FROM featured_messages 
            WHERE {where_clause}
        ''', params)
        total_records = cursor.fetchone()[0]
        
        # 计算总页数
        total_pages = (total_records + per_page - 1) // per_page
        
        # 获取当前页数据
        offset = (page - 1) * per_page
        cursor.execute(f'''
            SELECT 
                featured_by_id,
                COUNT(DISTINCT author_id) as referral_count
            FROM featured_messages 
            WHERE {where_clause}
            GROUP BY featured_by_id
            ORDER BY referral_count DESC
            LIMIT ? OFFSET ?
        ''', params + [per_page, offset])
        
        results = cursor.fetchall()
        
        # 获取用户名
        ranking_data = []
        for row in results:
            user_id = row[0]
            referral_count = row[1]
            # 从featured_messages表获取用户名
            cursor.execute('''
                SELECT featured_by_name FROM featured_messages 
                WHERE featured_by_id = ? AND guild_id = ?
                LIMIT 1
            ''', (user_id, guild_id))
            name_result = cursor.fetchone()
            username = name_result[0] if name_result else f"用户{user_id}"
            
            ranking_data.append({
                'user_id': user_id,
                'username': username,
                'referral_count': referral_count
            })
        
        conn.close()
        return ranking_data, total_pages 

    def get_all_featured_messages(self, guild_id: int, page: int = 1, per_page: int = 10, 
                                 sort_by: str = "time", start_date: str = None, end_date: str = None) -> Tuple[List[Dict], int]:
        """获取全服精選留言数据（分页，支持时间范围和时间/讚数排序）"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 构建查询条件
        where_conditions = ["guild_id = ?"]
        params = [guild_id]
        
        if start_date:
            where_conditions.append("featured_at >= ?")
            params.append(start_date)
        
        if end_date:
            where_conditions.append("featured_at <= ?")
            params.append(end_date)
        
        where_clause = " AND ".join(where_conditions)
        
        # 获取总记录数
        cursor.execute(f'SELECT COUNT(*) FROM featured_messages WHERE {where_clause}', params)
        total_records = cursor.fetchone()[0]
        
        # 计算总页数
        total_pages = (total_records + per_page - 1) // per_page
        
        # 确定排序方式
        if sort_by == "reactions":
            # 讚数排序（这里先按时间排序，讚数会在应用层处理）
            order_clause = "featured_at DESC"
        else:
            # 时间排序（默认）
            order_clause = "featured_at DESC"
        
        # 获取当前页数据
        offset = (page - 1) * per_page
        cursor.execute(f'''
            SELECT 
                id, thread_id, message_id, author_id, author_name, 
                featured_by_id, featured_by_name, featured_at, reason
            FROM featured_messages 
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
        ''', params + [per_page, offset])
        
        results = cursor.fetchall()
        conn.close()
        
        # 转换为字典格式
        messages = [
            {
                'id': row[0],
                'thread_id': row[1],
                'message_id': row[2],
                'author_id': row[3],
                'author_name': row[4],
                'featured_by_id': row[5],
                'featured_by_name': row[6],
                'featured_at': row[7],
                'reason': row[8]
            }
            for row in results
        ]
        
        return messages, total_pages

    # ==================== 书单 2.0 ====================
    def ensure_user_booklists(self, user_id: int):
        """确保用户拥有 0~9 共 10 张书单。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        for list_id in range(10):
            cursor.execute('''
                INSERT OR IGNORE INTO user_booklists (user_id, list_id, title)
                VALUES (?, ?, ?)
            ''', (user_id, list_id, f"我的书单 {list_id}"))

        conn.commit()
        conn.close()

    def get_user_booklists_overview(self, user_id: int) -> List[Dict]:
        """获取用户 10 张书单概览（标题 + 帖子数）。"""
        self.ensure_user_booklists(user_id)

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                b.list_id,
                b.title,
                COUNT(e.id) AS post_count
            FROM user_booklists b
            LEFT JOIN user_booklist_entries e
                ON b.user_id = e.user_id AND b.list_id = e.list_id
            WHERE b.user_id = ?
            GROUP BY b.user_id, b.list_id, b.title
            ORDER BY b.list_id ASC
        ''', (user_id,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {'list_id': row[0], 'title': row[1], 'post_count': row[2]}
            for row in rows
        ]

    def get_user_booklist(self, user_id: int, list_id: int) -> Dict:
        """获取单张书单详情。"""
        self.ensure_user_booklists(user_id)

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT title FROM user_booklists
            WHERE user_id = ? AND list_id = ?
        ''', (user_id, list_id))
        title_row = cursor.fetchone()

        cursor.execute('''
            SELECT id, thread_guild_id, thread_id, thread_title, thread_url, review, added_at
            FROM user_booklist_entries
            WHERE user_id = ? AND list_id = ?
            ORDER BY added_at DESC, id DESC
        ''', (user_id, list_id))
        entry_rows = cursor.fetchall()
        conn.close()

        entries = [
            {
                'id': row[0],
                'thread_guild_id': row[1],
                'thread_id': row[2],
                'thread_title': row[3],
                'thread_url': row[4],
                'review': row[5] or "",
                'added_at': row[6]
            }
            for row in entry_rows
        ]

        return {
            'list_id': list_id,
            'title': title_row[0] if title_row else f"我的书单 {list_id}",
            'post_count': len(entries),
            'entries': entries
        }

    def rename_user_booklist(self, user_id: int, list_id: int, new_title: str):
        """重命名书单标题。"""
        self.ensure_user_booklists(user_id)

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_booklists
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND list_id = ?
        ''', (new_title, user_id, list_id))
        conn.commit()
        conn.close()

    def add_post_to_booklist(self, user_id: int, list_id: int, thread_guild_id: int, thread_id: int,
                             thread_title: str, thread_url: str, review: str = "") -> Tuple[bool, str]:
        """添加帖子到书单（同书单不重复，最多 20 条）。"""
        if list_id < 0 or list_id > 9:
            return False, "书单 ID 必须在 0~9。"

        self.ensure_user_booklists(user_id)

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*)
            FROM user_booklist_entries
            WHERE user_id = ? AND list_id = ?
        ''', (user_id, list_id))
        current_count = cursor.fetchone()[0]
        if current_count >= 20:
            conn.close()
            return False, "该书单已满（20/20），无法继续添加。"

        cursor.execute('''
            SELECT 1
            FROM user_booklist_entries
            WHERE user_id = ? AND list_id = ? AND thread_id = ?
        ''', (user_id, list_id, thread_id))
        if cursor.fetchone():
            conn.close()
            return False, "同一书单内不能重复添加同一帖子。"

        try:
            cursor.execute('''
                INSERT INTO user_booklist_entries
                (user_id, list_id, thread_guild_id, thread_id, thread_title, thread_url, review)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, list_id, thread_guild_id, thread_id, thread_title, thread_url, review))
            conn.commit()
            conn.close()
            return True, "已成功添加到书单。"
        except sqlite3.IntegrityError:
            conn.close()
            return False, "同一书单内不能重复添加同一帖子。"

    def _get_entry_by_index(self, cursor, user_id: int, list_id: int, entry_index: int):
        if entry_index < 1:
            return None

        cursor.execute('''
            SELECT id, thread_id, thread_title, thread_url, review
            FROM user_booklist_entries
            WHERE user_id = ? AND list_id = ?
            ORDER BY added_at DESC, id DESC
            LIMIT 1 OFFSET ?
        ''', (user_id, list_id, entry_index - 1))
        return cursor.fetchone()

    def remove_booklist_entry_by_index(self, user_id: int, list_id: int, entry_index: int) -> Tuple[bool, str]:
        """按当前书单展示顺序删除第 N 条。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        entry = self._get_entry_by_index(cursor, user_id, list_id, entry_index)
        if not entry:
            conn.close()
            return False, "找不到对应序号的帖子。"

        cursor.execute('DELETE FROM user_booklist_entries WHERE id = ?', (entry[0],))
        conn.commit()
        conn.close()
        return True, f"已删除帖子：{entry[2]}"

    def move_booklist_entry_by_index(self, user_id: int, from_list_id: int, entry_index: int, to_list_id: int) -> Tuple[bool, str]:
        """将 from_list 的第 N 条移动到 to_list。"""
        if to_list_id < 0 or to_list_id > 9:
            return False, "目标书单 ID 必须在 0~9。"
        if from_list_id == to_list_id:
            return False, "来源书单与目标书单不能相同。"

        self.ensure_user_booklists(user_id)

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        entry = self._get_entry_by_index(cursor, user_id, from_list_id, entry_index)
        if not entry:
            conn.close()
            return False, "找不到对应序号的帖子。"

        thread_id = entry[1]
        thread_title = entry[2]

        cursor.execute('''
            SELECT COUNT(*)
            FROM user_booklist_entries
            WHERE user_id = ? AND list_id = ?
        ''', (user_id, to_list_id))
        to_count = cursor.fetchone()[0]
        if to_count >= 20:
            conn.close()
            return False, "目标书单已满（20/20），无法搬移。"

        cursor.execute('''
            SELECT 1
            FROM user_booklist_entries
            WHERE user_id = ? AND list_id = ? AND thread_id = ?
        ''', (user_id, to_list_id, thread_id))
        if cursor.fetchone():
            conn.close()
            return False, "目标书单已存在同一帖子，无法重复搬移。"

        cursor.execute('''
            UPDATE user_booklist_entries
            SET list_id = ?
            WHERE id = ?
        ''', (to_list_id, entry[0]))
        conn.commit()
        conn.close()
        return True, f"已将《{thread_title}》搬移到书单 {to_list_id}。"

    def update_booklist_entry_review_by_index(self, user_id: int, list_id: int, entry_index: int, new_review: str) -> Tuple[bool, str]:
        """按序号更新帖子评价。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        entry = self._get_entry_by_index(cursor, user_id, list_id, entry_index)
        if not entry:
            conn.close()
            return False, "找不到对应序号的帖子。"

        cursor.execute('''
            UPDATE user_booklist_entries
            SET review = ?
            WHERE id = ?
        ''', (new_review, entry[0]))
        conn.commit()
        conn.close()
        return True, "帖子评价已更新。"

    def create_public_booklist_record(self, user_id: int, list_id: int, guild_id: int,
                                      channel_id: int, message_id: int, intro: str):
        """记录公开书单消息，便于追踪/下架。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO public_booklists
            (user_id, list_id, guild_id, channel_id, message_id, intro)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, list_id, guild_id, channel_id, message_id, intro))
        conn.commit()
        conn.close()

    def deactivate_public_booklist(self, user_id: int, message_id: int) -> bool:
        """下架公开书单（仅发布者）。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE public_booklists
            SET is_active = 0, removed_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND message_id = ? AND is_active = 1
        ''', (user_id, message_id))
        changed = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return changed

    def set_user_booklist_thread_url(self, user_id: int, guild_id: int, thread_url: str):
        """设置或更新用户书单帖链接；空值视为删除。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        if not thread_url or not thread_url.strip():
            cursor.execute('''
                DELETE FROM user_booklist_thread_links
                WHERE user_id = ? AND guild_id = ?
            ''', (user_id, guild_id))
            conn.commit()
            conn.close()
            return

        cursor.execute('''
            INSERT INTO user_booklist_thread_links (user_id, guild_id, thread_url)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                thread_url = excluded.thread_url,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, guild_id, thread_url.strip()))

        conn.commit()
        conn.close()

    def get_user_booklist_thread_url(self, user_id: int, guild_id: int) -> Optional[str]:
        """获取用户在指定群组绑定的书单帖链接。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT thread_url
            FROM user_booklist_thread_links
            WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def get_booklist_thread_owner(self, guild_id: int, thread_id: int) -> Optional[int]:
        """根据群组+帖子ID查找书单帖绑定人（楼主）。没有则返回 None。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, thread_url
            FROM user_booklist_thread_links
            WHERE guild_id = ?
        ''', (guild_id,))
        rows = cursor.fetchall()
        conn.close()

        for user_id, thread_url in rows:
            if not thread_url:
                continue
            match = re.match(r"^https://discord\.com/channels/(\d+)/(\d+)(?:/\d+)?$", thread_url.strip())
            if not match:
                continue
            parsed_guild = int(match.group(1))
            parsed_thread = int(match.group(2))
            if parsed_guild == guild_id and parsed_thread == thread_id:
                return user_id
        return None

    def add_public_booklist_index(self, message_id: int, publisher_user_id: int, list_id: int,
                                  guild_id: int, channel_id: int):
        """保存公开书单最小索引。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO public_booklist_indexes
            (message_id, publisher_user_id, list_id, guild_id, channel_id, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(message_id) DO UPDATE SET
                publisher_user_id = excluded.publisher_user_id,
                list_id = excluded.list_id,
                guild_id = excluded.guild_id,
                channel_id = excluded.channel_id,
                is_active = 1
        ''', (message_id, publisher_user_id, list_id, guild_id, channel_id))
        conn.commit()
        conn.close()

    def get_active_public_booklist_indexes(self) -> List[Dict]:
        """获取所有仍激活的公开书单索引。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT message_id, publisher_user_id, list_id, guild_id, channel_id
            FROM public_booklist_indexes
            WHERE is_active = 1
            ORDER BY published_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'message_id': row[0],
                'publisher_user_id': row[1],
                'list_id': row[2],
                'guild_id': row[3],
                'channel_id': row[4],
            }
            for row in rows
        ]

    def deactivate_public_booklist_index(self, message_id: int):
        """移除公开书单索引（消息被删除或不可访问时）。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM public_booklist_indexes
            WHERE message_id = ?
        ''', (message_id,))
        conn.commit()
        conn.close()

    def get_guild_booklist_summary(self, guild_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
        """获取本服书单概览：至少有 1 帖书单内容的用户。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM (
                SELECT user_id
                FROM user_booklist_entries
                WHERE thread_guild_id = ?
                GROUP BY user_id
            ) t
        ''', (guild_id,))
        total_users = cursor.fetchone()[0]
        total_pages = (total_users + per_page - 1) // per_page if total_users > 0 else 1

        offset = (page - 1) * per_page
        cursor.execute('''
            SELECT
                user_id,
                COUNT(DISTINCT list_id) AS active_list_count,
                COUNT(*) AS total_posts
            FROM user_booklist_entries
            WHERE thread_guild_id = ?
            GROUP BY user_id
            ORDER BY total_posts DESC, user_id ASC
            LIMIT ? OFFSET ?
        ''', (guild_id, per_page, offset))
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'user_id': row[0],
                'active_list_count': row[1],
                'total_posts': row[2]
            }
            for row in rows
        ], total_pages

    def set_booklist_thread_whitelist(self, guild_id: int, forum_channel_id: int):
        """设置本服书单帖白名单论坛频道。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO booklist_thread_whitelist (guild_id, forum_channel_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id) DO UPDATE SET
                forum_channel_id = excluded.forum_channel_id,
                updated_at = CURRENT_TIMESTAMP
        ''', (guild_id, forum_channel_id))
        conn.commit()
        conn.close()

    def get_booklist_thread_whitelist(self, guild_id: int) -> Optional[int]:
        """获取本服书单帖白名单论坛频道ID。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT forum_channel_id
            FROM booklist_thread_whitelist
            WHERE guild_id = ?
        ''', (guild_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def clear_booklist_thread_whitelist(self, guild_id: int):
        """清除本服书单帖白名单。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM booklist_thread_whitelist
            WHERE guild_id = ?
        ''', (guild_id,))
        conn.commit()
        conn.close()

    def clear_all_booklist_thread_links_in_guild(self, guild_id: int) -> int:
        """清除本服所有用户书单帖链接绑定，返回清除条数。"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM user_booklist_thread_links
            WHERE guild_id = ?
        ''', (guild_id,))
        affected = cursor.rowcount if cursor.rowcount is not None else 0
        conn.commit()
        conn.close()
        return affected
