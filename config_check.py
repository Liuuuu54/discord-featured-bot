#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置验证脚本
用于检查 Discord Bot 的配置是否正确
"""

import os
import sys
from pathlib import Path

def check_env_file():
    """检查 .env 文件"""
    print("🔍 检查 .env 文件...")
    
    if not os.path.exists('.env'):
        print("❌ .env 文件不存在")
        print("💡 请复制 env_example.txt 为 .env 文件")
        return False
    
    print("✅ .env 文件存在")
    return True

def check_config_file():
    """检查 config.py 文件"""
    print("\n🔍 检查 config.py 文件...")
    
    if not os.path.exists('config.py'):
        print("❌ config.py 文件不存在")
        return False
    
    print("✅ config.py 文件存在")
    return True

def test_config_import():
    """测试配置导入"""
    print("\n🔍 测试配置导入...")
    
    try:
        import config
        print("✅ 配置导入成功")
        return True
    except Exception as e:
        print(f"❌ 配置导入失败: {e}")
        return False

def check_discord_token():
    """检查 Discord Token"""
    print("\n🔍 检查 Discord Token...")
    
    try:
        import config
        if config.DISCORD_TOKEN:
            if len(config.DISCORD_TOKEN) > 10:
                print(f"✅ Discord Token 已设置 ({config.DISCORD_TOKEN[:10]}...)")
                return True
            else:
                print("❌ Discord Token 格式不正确")
                return False
        else:
            print("❌ Discord Token 未设置")
            return False
    except Exception as e:
        print(f"❌ 检查 Discord Token 失败: {e}")
        return False

def check_directories():
    """检查必要目录"""
    print("\n🔍 检查必要目录...")
    
    try:
        import config
        directories = [
            config.DATA_DIR,
            config.LOGS_DIR
        ]
        
        for directory in directories:
            if os.path.exists(directory):
                print(f"✅ 目录存在: {directory}")
            else:
                print(f"⚠️ 目录不存在，将自动创建: {directory}")
        
        return True
    except Exception as e:
        print(f"❌ 检查目录失败: {e}")
        return False

def show_config_summary():
    """显示配置摘要"""
    print("\n📋 配置摘要:")
    
    try:
        import config
        
        config_items = [
            ("Discord Token", "已设置" if config.DISCORD_TOKEN else "未设置"),
            ("管理組角色長度", str(len(config.ADMIN_ROLE_NAMES))),
            ("界面超时", f"{config.VIEW_TIMEOUT} 秒"),
            ("用户记录每页", f"{config.USER_RECORDS_PER_PAGE} 条"),
            ("排行榜每页", f"{config.RANKING_PER_PAGE} 条"),
            ("帖子统计每页", f"{config.THREAD_STATS_PER_PAGE} 条"),
            ("全服精选每页", f"{config.RECORDS_PER_PAGE} 条"),
            ("表情缓存时间", f"{config.REACTION_CACHE_DURATION} 秒"),
            ("日志级别", config.LOG_LEVEL),
            ("日志输出到控制台", "是" if config.LOG_TO_CONSOLE else "否"),
            ("最小消息长度", f"{config.MIN_MESSAGE_LENGTH} 字符"),
            ("最大消息长度", f"{config.MAX_MESSAGE_LENGTH} 字符" if config.MAX_MESSAGE_LENGTH > 0 else "无限制"),
            ("鉴赏家角色", config.APPRECIATOR_ROLE_NAME),
            ("鉴赏家最低被引荐", f"{config.APPRECIATOR_MIN_FEATURED} 次"),
            ("鉴赏家最低引荐", f"{config.APPRECIATOR_MIN_REFERRALS} 人"),
        ]
        
        for name, value in config_items:
            print(f"  {name}: {value}")
        
        print(f"\n管理组角色: {', '.join(config.ADMIN_ROLE_NAMES)}")
        
    except Exception as e:
        print(f"❌ 显示配置摘要失败: {e}")

def main():
    """主函数"""
    print("🤖 Discord Bot 配置检查工具")
    print("=" * 50)
    
    checks = [
        check_env_file,
        check_config_file,
        test_config_import,
        check_discord_token,
        check_directories,
    ]
    
    passed = 0
    total = len(checks)
    
    for check in checks:
        if check():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"检查结果: {passed}/{total} 项通过")
    
    if passed == total:
        print("🎉 所有检查都通过了！配置正确。")
        show_config_summary()
    else:
        print("⚠️ 部分检查未通过，请根据上述提示修复配置。")
        print("\n💡 提示:")
        print("1. 确保已创建 .env 文件并设置 DISCORD_TOKEN")
        print("2. 检查 config.py 文件是否存在且语法正确")
        print("3. 参考 CONFIG_GUIDE.md 了解详细配置说明")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
