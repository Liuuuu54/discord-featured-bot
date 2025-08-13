#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理月度積分表 - 臨時腳本
由於月排行功能已整合到總排行中，月度積分表不再需要
"""

import sqlite3
import os
from datetime import datetime

def cleanup_monthly_points():
    """清理月度積分表"""
    print("🧹 開始清理月度積分表...")
    
    # 數據庫文件路徑
    db_file = "data/featured_messages.db"
    
    # 檢查數據庫文件是否存在
    if not os.path.exists(db_file):
        print(f"❌ 數據庫文件不存在: {db_file}")
        return False
    
    try:
        # 連接數據庫
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 檢查月度積分表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='monthly_points'
        """)
        
        if not cursor.fetchone():
            print("ℹ️ 月度積分表不存在，無需清理")
            conn.close()
            return True
        
        # 獲取月度積分表的統計信息
        cursor.execute("SELECT COUNT(*) FROM monthly_points")
        total_records = cursor.fetchone()[0]
        
        if total_records == 0:
            print("ℹ️ 月度積分表為空，無需清理")
            conn.close()
            return True
        
        print(f"📊 月度積分表統計:")
        print(f"  - 總記錄數: {total_records}")
        
        # 顯示一些示例數據
        cursor.execute("""
            SELECT year_month, COUNT(*) as count, SUM(points) as total_points
            FROM monthly_points 
            GROUP BY year_month 
            ORDER BY year_month DESC 
            LIMIT 5
        """)
        
        sample_data = cursor.fetchall()
        if sample_data:
            print("  - 示例數據:")
            for year_month, count, total_points in sample_data:
                print(f"    * {year_month}: {count} 用戶, {total_points or 0} 總積分")
        
        # 確認是否要清理
        print("\n⚠️ 警告: 此操作將永久刪除月度積分表的所有數據！")
        print("由於月排行功能已整合到總排行中，月度積分表不再需要。")
        
        confirm = input("\n是否確定要刪除月度積分表？(輸入 'yes' 確認): ")
        
        if confirm.lower() != 'yes':
            print("❌ 操作已取消")
            conn.close()
            return False
        
        # 刪除月度積分表
        print("\n🗑️ 正在刪除月度積分表...")
        cursor.execute("DROP TABLE monthly_points")
        
        # 提交更改
        conn.commit()
        
        # 驗證表是否已被刪除
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='monthly_points'
        """)
        
        if not cursor.fetchone():
            print("✅ 月度積分表已成功刪除")
        else:
            print("❌ 月度積分表刪除失敗")
            conn.close()
            return False
        
        # 顯示清理後的數據庫狀態
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"\n📋 清理後的數據庫表:")
        for table in tables:
            print(f"  - {table[0]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 清理過程中發生錯誤: {e}")
        return False

def backup_monthly_points():
    """備份月度積分表（可選）"""
    print("\n💾 是否要備份月度積分表？")
    print("備份文件將保存為 CSV 格式，包含所有月度積分數據")
    
    confirm = input("是否要備份？(輸入 'yes' 備份): ")
    
    if confirm.lower() != 'yes':
        print("跳過備份")
        return True
    
    try:
        import csv
        
        db_file = "data/featured_messages.db"
        backup_file = f"monthly_points_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 檢查表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='monthly_points'
        """)
        
        if not cursor.fetchone():
            print("❌ 月度積分表不存在，無法備份")
            conn.close()
            return False
        
        # 獲取所有數據
        cursor.execute("""
            SELECT user_id, guild_id, username, points, year_month, created_at, updated_at
            FROM monthly_points
            ORDER BY year_month DESC, points DESC
        """)
        
        data = cursor.fetchall()
        
        if not data:
            print("ℹ️ 月度積分表為空，無需備份")
            conn.close()
            return True
        
        # 寫入CSV文件
        with open(backup_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # 寫入標題行
            writer.writerow(['用戶ID', '群組ID', '用戶名', '積分', '年月', '創建時間', '更新時間'])
            
            # 寫入數據
            for row in data:
                writer.writerow(row)
        
        print(f"✅ 備份完成: {backup_file}")
        print(f"  - 備份記錄數: {len(data)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 備份過程中發生錯誤: {e}")
        return False

def main():
    """主函數"""
    print("=" * 60)
    print("🧹 月度積分表清理工具")
    print("=" * 60)
    print("此工具將清理不再需要的月度積分表")
    print("由於月排行功能已整合到總排行中，月度積分表不再需要")
    print("=" * 60)
    
    # 首先詢問是否要備份
    if not backup_monthly_points():
        print("❌ 備份失敗，停止清理")
        return
    
    # 執行清理
    if cleanup_monthly_points():
        print("\n🎉 清理完成！")
        print("月度積分表已成功刪除，數據庫已優化")
    else:
        print("\n❌ 清理失敗！")
        print("請檢查錯誤信息並重試")

if __name__ == "__main__":
    main()
