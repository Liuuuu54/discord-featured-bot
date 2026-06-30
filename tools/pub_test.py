"""书单发布接口自测脚本。

用法（在容器内运行；密钥从容器环境变量 BOOKLIST_API_SECRET 读取）：
    python /tmp/pt.py <thread_url> <discord_user_id> [booklist_id]

示例：
    docker cp tools/pub_test.py dc-bot:/tmp/pt.py
    docker exec dc-bot python /tmp/pt.py 'https://discord.com/channels/G/T' 123456 999001
"""
import json
import os
import sys
import urllib.error
import urllib.request

if len(sys.argv) < 3:
    print("usage: python pt.py <thread_url> <discord_user_id> [booklist_id]")
    sys.exit(1)

thread_url = sys.argv[1]
discord_user_id = sys.argv[2]
booklist_id = int(sys.argv[3]) if len(sys.argv) > 3 else 999001

secret = os.environ.get("BOOKLIST_API_SECRET", "")
if not secret:
    print("ERROR: BOOKLIST_API_SECRET not set in environment")
    sys.exit(1)

port = os.environ.get("BOOKLIST_API_PORT", "10820")
body = json.dumps({
    "booklist_id": booklist_id,
    "thread_url": thread_url,
    "discord_user_id": discord_user_id,
    "title": "test booklist",
    "description": "endpoint self-test",
    "items": [
        {"title": "test post A", "url": "https://example.com/a", "review": "ok"},
        {"title": "test post B", "url": "https://example.com/b", "review": ""},
    ],
}).encode()

req = urllib.request.Request(
    f"http://localhost:{port}/booklist/publish",
    data=body,
    headers={"Content-Type": "application/json", "X-API-Key": secret},
    method="POST",
)
try:
    print(urllib.request.urlopen(req).read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
