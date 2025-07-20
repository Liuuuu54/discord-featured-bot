#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康檢查服務器
用於 Railway 健康檢查
"""

import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                "status": "healthy",
                "service": "Discord Bot",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "uptime": time.time()
            }
            
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
    
    def log_message(self, format, *args):
        # 禁用訪問日誌
        pass

def start_health_server(port=8080):
    """啟動健康檢查服務器"""
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"🏥 健康檢查服務器啟動在端口 {port}")
        server.serve_forever()
    except Exception as e:
        print(f"❌ 健康檢查服務器啟動失敗: {e}")

if __name__ == "__main__":
    # 從環境變量獲取端口
    port = int(os.environ.get('PORT', 8080))
    start_health_server(port) 