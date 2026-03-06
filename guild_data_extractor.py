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
        self.cursor.execute("SELECT DISTINCT guild_id FROM featured_messages ORDER BY guild_id")
        guilds = [row[0] for row in self.cursor.fetchall()]
        return guilds
    
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
        
        return {
            'guild_id': guild_id,
            'user_count': user_stats[0] if user_stats else 0,
            'featured_count': featured_count
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
    
    def extract_all_guild_data(self, guild_id: int) -> Dict[str, Any]:
        """提取群组所有数据"""
        print(f"🔍 正在提取群组 {guild_id} 的数据...")
        
        guild_info = self.get_guild_info(guild_id)
        featured_messages = self.extract_featured_messages(guild_id)
        
        return {
            'guild_info': guild_info,
            'featured_messages': featured_messages,
            'extract_time': datetime.now().isoformat(),
            'total_records': {
                'featured_messages': len(featured_messages)
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
        print("-"*50)
        print(f"📋 提取记录数:")
        print(f"   - 精選记录: {total_records['featured_messages']}")
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