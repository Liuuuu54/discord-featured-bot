import sqlite3
import os

def clean_database(db_path='data/featured_messages.db'):
    print("🤖 Discord Bot 資料庫清理工具 (移除積分系統)")
    print("=" * 50)
    
    if not os.path.exists(db_path):
        print(f"❌ 找不到資料庫檔案: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 檢查 user_points 資料表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_points'")
        if cursor.fetchone():
            print("⏳ 正在移除 user_points 資料表...")
            cursor.execute("DROP TABLE user_points")
            conn.commit()
            print("✅ 成功移除 user_points 資料表！")
        else:
            print("ℹ️ 資料庫中已不存在 user_points 資料表，無需清理。")
            
        # 執行 VACUUM 以釋放空間
        print("⏳ 正在最佳化資料庫空間 (VACUUM)...")
        cursor.execute("VACUUM")
        conn.commit()
        print("✅ 資料庫最佳化完成！")
        
        conn.close()
        print("\n🎉 資料庫清理作業完成！積分相關資料已完全刪除。")
        
    except Exception as e:
        print(f"❌ 清理過程中發生錯誤: {e}")

if __name__ == '__main__':
    clean_database()
