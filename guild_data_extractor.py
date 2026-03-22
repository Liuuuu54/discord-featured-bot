#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
群组数据提取工具
用于从数据库中提取指定群组的所有数据，支持导出为JSON、CSV等格式
"""

import sqlite3
import json
import csv
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

# 导入配置文件
try:
    import config
    db_file = config.DATABASE_FILE
except ImportError:
    # 如果无法导入config，使用默认路径
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    db_file = os.path.join(data_dir, 'featured_messages.db')

class GuildDataExtractor:
    """群组数据提取器"""
    
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """连接数据库"""
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.cursor = self.conn.cursor()
            print(f"✅ 成功连接到数据库: {self.db_file}")
        except Exception as e:
            print(f"❌ 连接数据库失败: {e}")
            sys.exit(1)
    
    def disconnect(self):
        """断开数据库连接"""
        if self.conn:
            self.conn.close()
            print("🔌 数据库连接已关闭")
    
    def get_all_guilds(self) -> List[int]:
        """获取所有群组ID"""
        guild_ids = set()

        # 精选主表
        try:
            self.cursor.execute("SELECT DISTINCT guild_id FROM featured_messages")
            guild_ids.update(row[0] for row in self.cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # 书单明细（按帖子所属群组）
        try:
            self.cursor.execute("SELECT DISTINCT thread_guild_id FROM user_booklist_entries")
            guild_ids.update(row[0] for row in self.cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # 书单帖绑定
        try:
            self.cursor.execute("SELECT DISTINCT guild_id FROM user_booklist_thread_links")
            guild_ids.update(row[0] for row in self.cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # 公开书单索引
        try:
            self.cursor.execute("SELECT DISTINCT guild_id FROM public_booklist_indexes")
            guild_ids.update(row[0] for row in self.cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        # 白名单配置
        try:
            self.cursor.execute("SELECT DISTINCT guild_id FROM booklist_thread_whitelist")
            guild_ids.update(row[0] for row in self.cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        return sorted(guild_ids)
    
    def get_guild_info(self, guild_id: int) -> Dict[str, Any]:
        """获取群组基本信息"""
        # 用户统计
        self.cursor.execute("""
            SELECT COUNT(DISTINCT author_id) as user_count 
            FROM featured_messages 
            WHERE guild_id = ?
        """, (guild_id,))
        user_stats = self.cursor.fetchone()
        
        # 精選记录统计
        self.cursor.execute("""
            SELECT COUNT(*) as featured_count 
            FROM featured_messages 
            WHERE guild_id = ?
        """, (guild_id,))
        featured_count = self.cursor.fetchone()[0]

        # 书单帖子统计（可能不存在该表，需兼容）
        booklist_post_count = 0
        try:
            self.cursor.execute("""
                SELECT COUNT(*) 
                FROM user_booklist_entries
                WHERE thread_guild_id = ?
            """, (guild_id,))
            booklist_post_count = self.cursor.fetchone()[0]
        except sqlite3.OperationalError:
            booklist_post_count = 0
        
        return {
            'guild_id': guild_id,
            'user_count': user_stats[0] if user_stats else 0,
            'featured_count': featured_count,
            'booklist_post_count': booklist_post_count
        }
    

    
    def extract_featured_messages(self, guild_id: int) -> List[Dict[str, Any]]:
        """提取群组精選记录数据"""
        self.cursor.execute("""
            SELECT id, thread_id, message_id, author_id, author_name, 
                   featured_by_id, featured_by_name, featured_at, reason, bot_message_id
            FROM featured_messages 
            WHERE guild_id = ?
            ORDER BY featured_at DESC
        """, (guild_id,))
        
        results = self.cursor.fetchall()
        return [
            {
                'id': row[0],
                'thread_id': row[1],
                'message_id': row[2],
                'author_id': row[3],
                'author_name': row[4],
                'featured_by_id': row[5],
                'featured_by_name': row[6],
                'featured_at': row[7],
                'reason': row[8],
                'bot_message_id': row[9]
            }
            for row in results
        ]

    def extract_booklist_entries(self, guild_id: int) -> List[Dict[str, Any]]:
        """提取群组相关书单帖子明细（按 thread_guild_id）。"""
        try:
            self.cursor.execute("""
                SELECT id, user_id, list_id, thread_guild_id, thread_id, thread_title, thread_url, review, added_at
                FROM user_booklist_entries
                WHERE thread_guild_id = ?
                ORDER BY added_at DESC
            """, (guild_id,))
            rows = self.cursor.fetchall()
        except sqlite3.OperationalError:
            return []

        return [
            {
                'id': row[0],
                'user_id': row[1],
                'list_id': row[2],
                'thread_guild_id': row[3],
                'thread_id': row[4],
                'thread_title': row[5],
                'thread_url': row[6],
                'review': row[7],
                'added_at': row[8],
            }
            for row in rows
        ]

    def extract_user_booklists(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        """提取指定用户的书单主表数据。"""
        if not user_ids:
            return []
        try:
            placeholders = ",".join(["?"] * len(user_ids))
            self.cursor.execute(f"""
                SELECT user_id, list_id, title, created_at, updated_at
                FROM user_booklists
                WHERE user_id IN ({placeholders})
                ORDER BY user_id, list_id
            """, tuple(user_ids))
            rows = self.cursor.fetchall()
        except sqlite3.OperationalError:
            return []

        return [
            {
                'user_id': row[0],
                'list_id': row[1],
                'title': row[2],
                'created_at': row[3],
                'updated_at': row[4],
            }
            for row in rows
        ]

    def extract_user_booklist_thread_links(self, guild_id: int) -> List[Dict[str, Any]]:
        """提取本群组书单帖绑定。"""
        try:
            self.cursor.execute("""
                SELECT user_id, guild_id, thread_url, updated_at
                FROM user_booklist_thread_links
                WHERE guild_id = ?
                ORDER BY updated_at DESC
            """, (guild_id,))
            rows = self.cursor.fetchall()
        except sqlite3.OperationalError:
            return []

        return [
            {
                'user_id': row[0],
                'guild_id': row[1],
                'thread_url': row[2],
                'updated_at': row[3],
            }
            for row in rows
        ]

    def extract_public_booklist_indexes(self, guild_id: int) -> List[Dict[str, Any]]:
        """提取本群组公开书单最小索引。"""
        try:
            self.cursor.execute("""
                SELECT message_id, publisher_user_id, list_id, guild_id, channel_id, published_at, is_active
                FROM public_booklist_indexes
                WHERE guild_id = ?
                ORDER BY published_at DESC
            """, (guild_id,))
            rows = self.cursor.fetchall()
        except sqlite3.OperationalError:
            return []

        return [
            {
                'message_id': row[0],
                'publisher_user_id': row[1],
                'list_id': row[2],
                'guild_id': row[3],
                'channel_id': row[4],
                'published_at': row[5],
                'is_active': row[6],
            }
            for row in rows
        ]

    def extract_booklist_thread_whitelist(self, guild_id: int) -> List[Dict[str, Any]]:
        """提取本群组书单帖白名单配置。"""
        try:
            self.cursor.execute("""
                SELECT guild_id, forum_channel_id, updated_at
                FROM booklist_thread_whitelist
                WHERE guild_id = ?
            """, (guild_id,))
            rows = self.cursor.fetchall()
        except sqlite3.OperationalError:
            return []

        return [
            {
                'guild_id': row[0],
                'forum_channel_id': row[1],
                'updated_at': row[2],
            }
            for row in rows
        ]
    
    def extract_all_guild_data(self, guild_id: int) -> Dict[str, Any]:
        """提取群组所有数据"""
        print(f"🔍 正在提取群组 {guild_id} 的数据...")
        
        guild_info = self.get_guild_info(guild_id)
        featured_messages = self.extract_featured_messages(guild_id)
        booklist_entries = self.extract_booklist_entries(guild_id)
        related_user_ids = sorted(list({x['user_id'] for x in booklist_entries}))
        user_booklists = self.extract_user_booklists(related_user_ids)
        user_booklist_thread_links = self.extract_user_booklist_thread_links(guild_id)
        public_booklist_indexes = self.extract_public_booklist_indexes(guild_id)
        booklist_thread_whitelist = self.extract_booklist_thread_whitelist(guild_id)
        
        return {
            'guild_info': guild_info,
            'featured_messages': featured_messages,
            'user_booklists': user_booklists,
            'user_booklist_entries': booklist_entries,
            'user_booklist_thread_links': user_booklist_thread_links,
            'public_booklist_indexes': public_booklist_indexes,
            'booklist_thread_whitelist': booklist_thread_whitelist,
            'extract_time': datetime.now().isoformat(),
            'total_records': {
                'featured_messages': len(featured_messages),
                'user_booklists': len(user_booklists),
                'user_booklist_entries': len(booklist_entries),
                'user_booklist_thread_links': len(user_booklist_thread_links),
                'public_booklist_indexes': len(public_booklist_indexes),
                'booklist_thread_whitelist': len(booklist_thread_whitelist),
            }
        }
    
    def save_to_json(self, data: Dict[str, Any], filename: str):
        """保存数据到JSON文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ 数据已保存到: {filename}")
        except Exception as e:
            print(f"❌ 保存JSON文件失败: {e}")
    
    def save_to_csv(self, data: Dict[str, Any], base_filename: str):
        """保存数据到CSV文件"""
        try:

            
            # 保存精選记录
            if data['featured_messages']:
                featured_messages_file = f"{base_filename}_featured_messages.csv"
                with open(featured_messages_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=data['featured_messages'][0].keys())
                    writer.writeheader()
                    writer.writerows(data['featured_messages'])
                print(f"✅ 精選记录已保存到: {featured_messages_file}")

            # 保存书单主表
            if data.get('user_booklists'):
                file_name = f"{base_filename}_user_booklists.csv"
                with open(file_name, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=data['user_booklists'][0].keys())
                    writer.writeheader()
                    writer.writerows(data['user_booklists'])
                print(f"✅ 书单主表已保存到: {file_name}")

            # 保存书单明细
            if data.get('user_booklist_entries'):
                file_name = f"{base_filename}_user_booklist_entries.csv"
                with open(file_name, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=data['user_booklist_entries'][0].keys())
                    writer.writeheader()
                    writer.writerows(data['user_booklist_entries'])
                print(f"✅ 书单明细已保存到: {file_name}")

            # 保存书单帖绑定
            if data.get('user_booklist_thread_links'):
                file_name = f"{base_filename}_user_booklist_thread_links.csv"
                with open(file_name, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=data['user_booklist_thread_links'][0].keys())
                    writer.writeheader()
                    writer.writerows(data['user_booklist_thread_links'])
                print(f"✅ 书单帖绑定已保存到: {file_name}")

            # 保存公开书单索引
            if data.get('public_booklist_indexes'):
                file_name = f"{base_filename}_public_booklist_indexes.csv"
                with open(file_name, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=data['public_booklist_indexes'][0].keys())
                    writer.writeheader()
                    writer.writerows(data['public_booklist_indexes'])
                print(f"✅ 公开书单索引已保存到: {file_name}")

            # 保存白名单
            if data.get('booklist_thread_whitelist'):
                file_name = f"{base_filename}_booklist_thread_whitelist.csv"
                with open(file_name, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=data['booklist_thread_whitelist'][0].keys())
                    writer.writeheader()
                    writer.writerows(data['booklist_thread_whitelist'])
                print(f"✅ 书单帖白名单已保存到: {file_name}")
                
        except Exception as e:
            print(f"❌ 保存CSV文件失败: {e}")
    
    def create_new_database(self, data: Dict[str, Any], db_filename: str):
        """创建新的数据库文件，包含指定群组的数据"""
        try:
            # 创建新数据库连接
            new_conn = sqlite3.connect(db_filename)
            new_cursor = new_conn.cursor()
            
            print(f"🔧 正在创建新数据库: {db_filename}")
            

            
            new_cursor.execute('''
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
            
            # 创建索引
            new_cursor.execute('CREATE INDEX IF NOT EXISTS idx_featured_messages_guild ON featured_messages(guild_id)')

            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_booklists (
                    user_id INTEGER NOT NULL,
                    list_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, list_id)
                )
            ''')

            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_booklist_entries (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    list_id INTEGER NOT NULL,
                    thread_guild_id INTEGER NOT NULL,
                    thread_id INTEGER NOT NULL,
                    thread_title TEXT NOT NULL,
                    thread_url TEXT NOT NULL,
                    review TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_booklist_thread_links (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    thread_url TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')

            new_cursor.execute('''
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

            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS booklist_thread_whitelist (
                    guild_id INTEGER PRIMARY KEY,
                    forum_channel_id INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            

            
            # 插入精選记录数据
            if data['featured_messages']:
                for featured_msg in data['featured_messages']:
                    new_cursor.execute('''
                        INSERT INTO featured_messages 
                        (guild_id, thread_id, message_id, author_id, author_name, 
                         featured_by_id, featured_by_name, featured_at, reason, bot_message_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data['guild_info']['guild_id'],
                        featured_msg['thread_id'],
                        featured_msg['message_id'],
                        featured_msg['author_id'],
                        featured_msg['author_name'],
                        featured_msg['featured_by_id'],
                        featured_msg['featured_by_name'],
                        featured_msg['featured_at'],
                        featured_msg['reason'],
                        featured_msg['bot_message_id']
                    ))
                print(f"✅ 已插入 {len(data['featured_messages'])} 条精選记录")

            if data.get('user_booklists'):
                for row in data['user_booklists']:
                    new_cursor.execute('''
                        INSERT INTO user_booklists (user_id, list_id, title, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        row['user_id'],
                        row['list_id'],
                        row['title'],
                        row['created_at'],
                        row['updated_at']
                    ))
                print(f"✅ 已插入 {len(data['user_booklists'])} 条书单主表记录")

            if data.get('user_booklist_entries'):
                for row in data['user_booklist_entries']:
                    new_cursor.execute('''
                        INSERT INTO user_booklist_entries
                        (id, user_id, list_id, thread_guild_id, thread_id, thread_title, thread_url, review, added_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['id'],
                        row['user_id'],
                        row['list_id'],
                        row['thread_guild_id'],
                        row['thread_id'],
                        row['thread_title'],
                        row['thread_url'],
                        row['review'],
                        row['added_at']
                    ))
                print(f"✅ 已插入 {len(data['user_booklist_entries'])} 条书单明细记录")

            if data.get('user_booklist_thread_links'):
                for row in data['user_booklist_thread_links']:
                    new_cursor.execute('''
                        INSERT INTO user_booklist_thread_links (user_id, guild_id, thread_url, updated_at)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        row['user_id'],
                        row['guild_id'],
                        row['thread_url'],
                        row['updated_at']
                    ))
                print(f"✅ 已插入 {len(data['user_booklist_thread_links'])} 条书单帖绑定记录")

            if data.get('public_booklist_indexes'):
                for row in data['public_booklist_indexes']:
                    new_cursor.execute('''
                        INSERT INTO public_booklist_indexes
                        (message_id, publisher_user_id, list_id, guild_id, channel_id, published_at, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['message_id'],
                        row['publisher_user_id'],
                        row['list_id'],
                        row['guild_id'],
                        row['channel_id'],
                        row['published_at'],
                        row['is_active']
                    ))
                print(f"✅ 已插入 {len(data['public_booklist_indexes'])} 条公开书单索引记录")

            if data.get('booklist_thread_whitelist'):
                for row in data['booklist_thread_whitelist']:
                    new_cursor.execute('''
                        INSERT INTO booklist_thread_whitelist (guild_id, forum_channel_id, updated_at)
                        VALUES (?, ?, ?)
                    ''', (
                        row['guild_id'],
                        row['forum_channel_id'],
                        row['updated_at']
                    ))
                print(f"✅ 已插入 {len(data['booklist_thread_whitelist'])} 条白名单记录")
            
            # 提交事务
            new_conn.commit()
            new_conn.close()
            
            print(f"✅ 新数据库创建成功: {db_filename}")
            
        except Exception as e:
            print(f"❌ 创建新数据库失败: {e}")
            if new_conn:
                new_conn.rollback()
                new_conn.close()
    
    def print_summary(self, data: Dict[str, Any]):
        """打印数据摘要"""
        guild_info = data['guild_info']
        total_records = data['total_records']
        
        print("\n" + "="*50)
        print(f"📊 群组 {guild_info['guild_id']} 数据摘要")
        print("="*50)
        print(f"👥 用户数量: {guild_info['user_count']}")
        print(f"🌟 精選记录: {guild_info['featured_count']}")
        print(f"📚 书单帖子: {guild_info.get('booklist_post_count', 0)}")
        print("-"*50)
        print(f"📋 提取记录数:")
        print(f"   - 精選记录: {total_records['featured_messages']}")
        print(f"   - 书单主表: {total_records.get('user_booklists', 0)}")
        print(f"   - 书单明细: {total_records.get('user_booklist_entries', 0)}")
        print(f"   - 书单帖绑定: {total_records.get('user_booklist_thread_links', 0)}")
        print(f"   - 公开书单索引: {total_records.get('public_booklist_indexes', 0)}")
        print(f"   - 书单帖白名单: {total_records.get('booklist_thread_whitelist', 0)}")
        print(f"⏰ 提取时间: {data['extract_time']}")
        print("="*50)

def main():
    """主函数"""
    print("🔧 群组数据提取工具")
    print("="*50)
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python guild_data_extractor.py <guild_id> [format]")
        print("")
        print("参数:")
        print("  guild_id: 要提取的群组ID")
        print("  format: 输出格式 (json/csv/db/both, 默认: both)")
        print("")
        print("示例:")
        print("  python guild_data_extractor.py 123456789")
        print("  python guild_data_extractor.py 123456789 json")
        print("  python guild_data_extractor.py 123456789 csv")
        print("  python guild_data_extractor.py 123456789 db")
        print("")
        print("特殊命令:")
        print("  python guild_data_extractor.py list    # 列出所有群组")
        print("  python guild_data_extractor.py all     # 提取所有群组数据")
        return
    
    command = sys.argv[1]
    output_format = sys.argv[2] if len(sys.argv) > 2 else 'both'
    
    # 创建提取器
    extractor = GuildDataExtractor(db_file)
    extractor.connect()
    
    try:
        if command == 'list':
            # 列出所有群组
            guilds = extractor.get_all_guilds()
            print(f"📋 数据库中共有 {len(guilds)} 个群组:")
            for guild_id in guilds:
                guild_info = extractor.get_guild_info(guild_id)
                print(f"  🏠 群组 {guild_id}: {guild_info['user_count']} 用户, {guild_info['featured_count']} 精選")
        
        elif command == 'all':
            # 提取所有群组数据
            guilds = extractor.get_all_guilds()
            print(f"🔄 开始提取所有 {len(guilds)} 个群组的数据...")
            
            for guild_id in guilds:
                data = extractor.extract_all_guild_data(guild_id)
                extractor.print_summary(data)
                
                # 保存数据
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_filename = f"guild_{guild_id}_{timestamp}"
                
                if output_format in ['json', 'both']:
                    json_filename = f"{base_filename}.json"
                    extractor.save_to_json(data, json_filename)
                
                if output_format in ['csv', 'both']:
                    extractor.save_to_csv(data, base_filename)
                
                if output_format in ['db', 'both']:
                    db_filename = f"{base_filename}.db"
                    extractor.create_new_database(data, db_filename)
                
                print()  # 空行分隔
        
        else:
            # 提取指定群组数据
            try:
                guild_id = int(command)
            except ValueError:
                print(f"❌ 无效的群组ID: {command}")
                return
            
            # 检查群组是否存在
            guilds = extractor.get_all_guilds()
            if guild_id not in guilds:
                print(f"❌ 群组 {guild_id} 在数据库中不存在")
                print(f"可用的群组: {guilds}")
                return
            
            # 提取数据
            data = extractor.extract_all_guild_data(guild_id)
            extractor.print_summary(data)
            
            # 保存数据
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"guild_{guild_id}_{timestamp}"
            
            if output_format in ['json', 'both']:
                json_filename = f"{base_filename}.json"
                extractor.save_to_json(data, json_filename)
            
            if output_format in ['csv', 'both']:
                extractor.save_to_csv(data, base_filename)
            
            if output_format in ['db', 'both']:
                db_filename = f"{base_filename}.db"
                extractor.create_new_database(data, db_filename)
    
    finally:
        extractor.disconnect()

if __name__ == "__main__":
    main() 
