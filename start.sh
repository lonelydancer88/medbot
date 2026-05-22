#!/bin/bash
set -e

# Check .env
if [ ! -f .env ]; then
    echo "请先创建 .env 文件：cp .env.example .env"
    echo "然后编辑 .env 填入 ANTHROPIC_API_KEY"
    exit 1
fi

# Install backend deps
echo "[1/3] 检查后端依赖..."
pip install -r requirements.txt -q 2>/dev/null

# Install frontend deps
echo "[2/3] 检查前端依赖..."
cd frontend && npm install --silent 2>/dev/null && cd ..

# Start both
echo "[3/3] 启动服务..."
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:5173"
echo ""
trap 'kill 0' EXIT
uvicorn backend.main:app --reload &
cd frontend && npm run dev &
wait
