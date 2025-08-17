#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
移除月度積分表腳本
安全地從數據庫中移除 monthly_points 表
"""

import sqlite3
import os
import sys
from datetime import datetime

# 導入配置文件
try:
    import config
    db_file = config.DATABASE_FILE
except ImportError:
    # 如果無法導入config，使用默認路徑
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    db_file = os.path.join(data_dir, 'featured_messages.db')

def print_separator(title):
    """打印分隔線"""
    print("\n" + "="*50)
    print(f" {title} ")
    print("="*50)

def backup_monthly_data():
    """備份月度積分數據（可選）"""
    print_separator("📋 月度積分數據備份")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 檢查月度積分表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monthly_points';")
        if not cursor.fetchone():
            print("❌ 月度積分表不存在，無需移除")
            conn.close()
            return False
        
        # 獲取月度積分數據
        cursor.execute("SELECT COUNT(*) FROM monthly_points;")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"📊 發現 {count} 條月度積分記錄")
            
            # 顯示前10條記錄作為備份參考
            cursor.execute("""
                SELECT user_id, username, points, year_month, created_at
                FROM monthly_points 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            records = cursor.fetchall()
            
            print("📝 前10條月度積分記錄（備份參考）:")
            for i, record in enumerate(records, 1):
                user_id, username, points, year_month, created_at = record
                print(f"  {i}. {username} (ID: {user_id}) - {points} 分 ({year_month}) - {created_at}")
            
            if count > 10:
                print(f"  ... 還有 {count - 10} 條記錄")
            
            # 詢問是否要備份
            response = input("\n❓ 是否要備份月度積分數據到文件？(y/N): ").strip().lower()
            if response == 'y':
                backup_file = f"monthly_points_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                
                cursor.execute("""
                    SELECT user_id, username, points, year_month, created_at, updated_at
                    FROM monthly_points 
                    ORDER BY created_at DESC
                """)
                all_records = cursor.fetchall()
                
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(f"月度積分數據備份 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*50 + "\n")
                    f.write("格式: user_id, username, points, year_month, created_at, updated_at\n")
                    f.write("="*50 + "\n")
                    
                    for record in all_records:
                        f.write(f"{','.join(map(str, record))}\n")
                
                print(f"✅ 月度積分數據已備份到: {backup_file}")
        else:
            print("📝 月度積分表為空，無需備份")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 備份月度積分數據時發生錯誤: {e}")
        return False

def remove_monthly_points_table():
    """移除月度積分表"""
    print_separator("🗑️ 移除月度積分表")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 檢查月度積分表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monthly_points';")
        if not cursor.fetchone():
            print("❌ 月度積分表不存在，無需移除")
            conn.close()
            return False
        
        # 獲取月度積分表信息
        cursor.execute("SELECT COUNT(*) FROM monthly_points;")
        count = cursor.fetchone()[0]
        
        print(f"📊 月度積分表包含 {count} 條記錄")
        
        # 確認移除
        response = input(f"\n⚠️ 確定要移除月度積分表嗎？這將永久刪除 {count} 條記錄！(y/N): ").strip().lower()
        if response != 'y':
            print("❌ 操作已取消")
            conn.close()
            return False
        
        # 開始事務
        cursor.execute("BEGIN TRANSACTION;")
        
        try:
            # 移除月度積分表
            cursor.execute("DROP TABLE IF EXISTS monthly_points;")
            
            # 提交事務
            cursor.execute("COMMIT;")
            
            print("✅ 月度積分表已成功移除")
            
            # 驗證移除結果
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monthly_points';")
            if not cursor.fetchone():
                print("✅ 驗證成功：月度積分表已不存在")
            else:
                print("❌ 驗證失敗：月度積分表仍然存在")
            
            conn.close()
            return True
            
        except Exception as e:
            # 回滾事務
            cursor.execute("ROLLBACK;")
            conn.close()
            print(f"❌ 移除月度積分表時發生錯誤: {e}")
            return False
        
    except Exception as e:
        print(f"❌ 連接數據庫時發生錯誤: {e}")
        return False

def verify_database():
    """驗證數據庫狀態"""
    print_separator("🔍 數據庫狀態驗證")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 獲取所有表格
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"📋 當前數據庫包含 {len(tables)} 個表格:")
        for table in tables:
            table_name = table[0]
            if table_name == 'sqlite_sequence':
                continue
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"  - {table_name}: {count} 條記錄")
        
        # 檢查月度積分表是否已移除
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monthly_points';")
        if not cursor.fetchone():
            print("✅ 月度積分表已成功移除")
        else:
            print("❌ 月度積分表仍然存在")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 驗證數據庫時發生錯誤: {e}")

def main():
    """主函數"""
    print_separator("🗑️ 月度積分表移除工具")
    print(f"數據庫文件: {db_file}")
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(db_file):
        print(f"❌ 數據庫文件 {db_file} 不存在！")
        return
    
    # 步驟1：備份數據（可選）
    if not backup_monthly_data():
        print("❌ 備份步驟失敗，停止操作")
        return
    
    # 步驟2：移除月度積分表
    if not remove_monthly_points_table():
        print("❌ 移除步驟失敗")
        return
    
    # 步驟3：驗證結果
    verify_database()
    
    print_separator("✅ 操作完成")
    print("💡 提示:")
    print("  - 月度積分表已從數據庫中移除")
    print("  - 如果已備份，備份文件保存在當前目錄")
    print("  - 機器人將不再使用月度積分功能")

if __name__ == "__main__":
    main()
