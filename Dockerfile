FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用代碼
COPY . .

# 創建數據目錄
RUN mkdir -p /app/data

# 設置環境變量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1


# 啟動命令
CMD ["python", "bot.py"] 