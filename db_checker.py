#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資料庫檢查工具
用於查看 Discord Bot 資料庫的內容
"""

import sqlite3
import os
from datetime import datetime

def print_separator(title):
    """打印分隔線"""
    print("\n" + "="*50)
    print(f" {title} ")
    print("="*50)

def check_database():
    """檢查資料庫內容"""
    db_file = "featured_messages.db"
    
    if not os.path.exists(db_file):
        print(f"❌ 資料庫文件 {db_file} 不存在！")
        return
    
    print_separator("📊 Discord Bot 資料庫檢查工具")
    print(f"資料庫文件: {db_file}")
    print(f"檢查時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 獲取所有表格
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\n📋 發現 {len(tables)} 個表格:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 檢查每個表格的內容
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
        
        # 特殊查詢：月度積分排行榜
        print_separator("🏆 月度積分排行榜")
        try:
            cursor.execute("""
                SELECT user_id, username, points, year_month
                FROM monthly_points 
                ORDER BY points DESC 
                LIMIT 10
            """)
            monthly_ranking = cursor.fetchall()
            
            if monthly_ranking:
                print("📊 月度積分排名:")
                for i, (user_id, username, points, year_month) in enumerate(monthly_ranking, 1):
                    rank_icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    print(f"  {rank_icon} {username} (ID: {user_id}) - {points} 分 ({year_month})")
            else:
                print("📝 還沒有月度積分記錄")
        except sqlite3.OperationalError:
            print("❌ 月度積分表格不存在")
        
        # 特殊查詢：總積分排行榜
        print_separator("📈 總積分排行榜")
        try:
            cursor.execute("""
                SELECT user_id, username, points
                FROM user_points 
                ORDER BY points DESC 
                LIMIT 10
            """)
            total_ranking = cursor.fetchall()
            
            if total_ranking:
                print("📊 總積分排名:")
                for i, (user_id, username, points) in enumerate(total_ranking, 1):
                    rank_icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    print(f"  {rank_icon} {username} (ID: {user_id}) - {points} 分")
            else:
                print("📝 還沒有總積分記錄")
        except sqlite3.OperationalError:
            print("❌ 用戶積分表格不存在")
        
        conn.close()
        print_separator("✅ 檢查完成")
        
    except Exception as e:
        print(f"❌ 檢查資料庫時發生錯誤: {e}")

def interactive_mode():
    """互動模式"""
    print_separator("🔧 互動式資料庫檢查")
    print("輸入 'q' 退出，輸入 'help' 查看幫助")
    
    try:
        conn = sqlite3.connect("featured_messages.db")
        cursor = conn.cursor()
        
        while True:
            try:
                query = input("\n🔍 輸入 SQL 查詢: ").strip()
                
                if query.lower() == 'q':
                    break
                elif query.lower() == 'help':
                    print("\n📖 常用查詢範例:")
                    print("  SELECT * FROM user_points LIMIT 5;")
                    print("  SELECT * FROM monthly_points ORDER BY points DESC LIMIT 10;")
                    print("  SELECT * FROM featured_messages LIMIT 5;")
                    print("  SELECT COUNT(*) FROM user_points;")
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

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        check_database()
        print("\n💡 提示: 使用 'python db_checker.py --interactive' 進入互動模式") 