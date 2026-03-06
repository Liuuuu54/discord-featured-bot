#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資料庫檢查工具
用於查看 Discord Bot 資料庫的內容（支持多群組）
支持簡單模式和詳細模式
"""

import sqlite3
import os
import sys
from datetime import datetime

# 导入配置文件
try:
    import config
    db_file = config.DATABASE_FILE
except ImportError:
    # 如果无法导入config，使用默认路径
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    db_file = os.path.join(data_dir, 'featured_messages.db')

def print_separator(title):
    """打印分隔線"""
    print("\n" + "="*50)
    print(f" {title} ")
    print("="*50)

def check_database(simple_mode=False):
    """檢查資料庫內容"""
    if not os.path.exists(db_file):
        print(f"❌ 資料庫文件 {db_file} 不存在！")
        return
    

    print(f"檢查時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"資料庫文件: {db_file}")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 獲取所有表格
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\n📋 發現 {len(tables)} 個表格:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 詳細模式：檢查每個表格的內容
        if not simple_mode:
            for table_name in [table[0] for table in tables]:
                print_separator(f"📋 表格: {table_name}")
                
                # 獲取表格結構
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                
                print("📐 表格結構:")
                for col in columns:
                    col_id, name, type_name, not_null, default_val, pk = col
                    pk_mark = " (主鍵)" if pk else ""
                    print(f"  - {name}: {type_name}{pk_mark}")
                
                # 獲取記錄數量
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                print(f"\n📊 記錄數量: {count} 條")
                
                if count > 0:
                    # 顯示前10條記錄
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 10;")
                    records = cursor.fetchall()
                    
                    print(f"\n📝 前 {min(10, count)} 條記錄:")
                    for i, record in enumerate(records, 1):
                        print(f"  {i}. {record}")
                    
                    if count > 10:
                        print(f"  ... 還有 {count - 10} 條記錄")
                
                print()
        
        
        # 精選記錄統計
        print_separator("🌟 精選記錄統計")
        try:
            cursor.execute("SELECT COUNT(*) FROM featured_messages")
            featured_count = cursor.fetchone()[0]
            print(f"📊 總精選記錄: {featured_count} 條")
            
            if featured_count > 0:
                cursor.execute("""
                    SELECT guild_id, COUNT(*) as count
                    FROM featured_messages 
                    GROUP BY guild_id
                    ORDER BY count DESC
                """)
                guild_featured = cursor.fetchall()
                
                print("📊 各群組精選記錄:")
                for guild_id, count in guild_featured:
                    print(f"  🏠 群組 {guild_id}: {count} 條")
        except sqlite3.OperationalError:
            print("❌ 精選記錄表格不存在")
        
        conn.close()
        print_separator("✅ 檢查完成")
        
    except Exception as e:
        print(f"❌ 檢查資料庫時發生錯誤: {e}")

def interactive_mode():
    """互動模式"""
    print_separator("🔧 互動式資料庫檢查")
    print("輸入 'q' 退出，輸入 'help' 查看幫助")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        print("✅ 數據庫支持多群組")
        print("💡 多群組查詢範例:")
        print("  SELECT * FROM featured_messages WHERE guild_id = 123456789;")
        print("  SELECT guild_id, COUNT(*) FROM featured_messages GROUP BY guild_id;")
        
        while True:
            try:
                query = input("\n🔍 輸入 SQL 查詢: ").strip()
                
                if query.lower() == 'q':
                    break
                elif query.lower() == 'help':
                    print("\n📖 常用查詢範例:")
                    print("  SELECT COUNT(*) FROM featured_messages;")
                    print("  SELECT author_id, COUNT(DISTINCT thread_id) FROM featured_messages GROUP BY author_id;")
                    print("\n🌐 多群組查詢:")
                    print("  SELECT * FROM featured_messages WHERE guild_id = 123456789;")
                    print("  SELECT guild_id, COUNT(*) FROM featured_messages GROUP BY guild_id;")
                    continue
                elif not query:
                    continue
                
                cursor.execute(query)
                results = cursor.fetchall()
                
                if results:
                    print(f"\n📊 查詢結果 ({len(results)} 條記錄):")
                    for i, row in enumerate(results, 1):
                        print(f"  {i}. {row}")
                else:
                    print("📝 查詢完成，沒有返回記錄")
                    
            except sqlite3.Error as e:
                print(f"❌ SQL 錯誤: {e}")
            except KeyboardInterrupt:
                break
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 連接資料庫時發生錯誤: {e}")

def check_guild_data(guild_id=None):
    """檢查特定群組的數據"""
    print_separator(f"🏠 群組數據檢查")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        if guild_id is None:
            # 顯示所有群組
            cursor.execute("SELECT DISTINCT guild_id FROM featured_messages ORDER BY guild_id")
            guilds = cursor.fetchall()
            
            if guilds:
                print("📋 發現的群組:")
                for (guild_id,) in guilds:
                    print(f"  - 群組 {guild_id}")
            else:
                print("📝 沒有群組數據")
            return
        
        # 檢查特定群組
        print(f"🔍 檢查群組 {guild_id} 的數據:")

        
        # 精選記錄
        cursor.execute("""
            SELECT author_name, featured_by_name, featured_at, reason
            FROM featured_messages 
            WHERE guild_id = ? 
            ORDER BY featured_at DESC
        """, (guild_id,))
        featured_messages = cursor.fetchall()
        
        print(f"\n🌟 精選記錄 ({len(featured_messages)} 條):")
        for author_name, featured_by_name, featured_at, reason in featured_messages[:10]:
            print(f"  - {author_name} 被 {featured_by_name} 精選 ({featured_at})")
            if reason:
                print(f"    原因: {reason}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 檢查群組數據時發生錯誤: {e}")

def print_usage():
    """打印使用說明"""
    print("用法:")
    print("  python db_checker.py                    # 詳細檢查")
    print("  python db_checker.py --simple           # 簡單檢查")
    print("  python db_checker.py --interactive      # 互動模式")
    print("  python db_checker.py --guild [群組ID]   # 檢查特定群組")
    print("\n參數說明:")
    print("  --simple      : 簡單模式，適合雲端環境")
    print("  --interactive : 互動模式，可輸入自定義 SQL")
    print("  --guild       : 檢查特定群組的數據")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--simple":
            check_database(simple_mode=True)
        elif sys.argv[1] == "--interactive":
            interactive_mode()
        elif sys.argv[1] == "--guild":
            guild_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
            check_guild_data(guild_id)
        elif sys.argv[1] in ["--help", "-h", "help"]:
            print_usage()
        else:
            print("❌ 未知參數")
            print_usage()
    else:
        check_database(simple_mode=False)
        print("\n💡 提示:")
        print("  - 使用 'python db_checker.py --simple' 進行簡單檢查")
        print("  - 使用 'python db_checker.py --interactive' 進入互動模式")
        print("  - 使用 'python db_checker.py --guild 123456789' 檢查特定群組")
        print("  - 使用 'python db_checker.py --help' 查看完整說明") 