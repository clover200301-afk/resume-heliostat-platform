#!/usr/bin/env bash
# 定日镜场在线仿真选址平台 —— 一键启动脚本
#
# 用法：
#   ./run.sh            自动挑一个可用端口（依次尝试 8000/8080/8888/9090/7860/4200/5555/9999）
#   ./run.sh 8080       显式指定端口

set -e
cd "$(dirname "$0")"

# ---------- 挑端口 ----------
if [ $# -ge 1 ]; then
  # 用户显式给了端口
  PORT="$1"
  if lsof -nP -i:"$PORT" 2>/dev/null | grep -q LISTEN; then
    echo "⚠️  端口 $PORT 已被占用。请传入其他端口，或直接 ./run.sh 自动挑选。"
    exit 1
  fi
else
  PORT=""
  for CAND in 8000 8080 8888 9090 7860 4200 5555 9999 18000 28000; do
    if ! lsof -nP -i:"$CAND" 2>/dev/null | grep -q LISTEN; then
      PORT="$CAND"; break
    fi
  done
  if [ -z "$PORT" ]; then
    echo "⚠️  常用端口全部被占，请手动指定：./run.sh <port>"
    exit 1
  fi
fi

echo "== 启动定日镜场在线仿真选址平台 =="
echo "  监听端口 : $PORT"
echo "  日志文件 : /tmp/heliostat_uvicorn.log"
echo ""

# 挑一个 Python：优先 Homebrew（用户之前的 pip 装在这），失败再退到 python3
if [ -x /opt/homebrew/bin/python3 ]; then
  PYBIN=/opt/homebrew/bin/python3
elif command -v python3 >/dev/null 2>&1; then
  PYBIN="$(command -v python3)"
else
  echo "⚠️  未找到 python3，请先安装 Python。"; exit 1
fi

# 检查 fastapi / uvicorn
if ! "$PYBIN" -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "⚙️  正在安装缺失依赖 (fastapi, uvicorn)…"
  "$PYBIN" -m pip install --user --break-system-packages fastapi uvicorn >/dev/null 2>&1 || {
    "$PYBIN" -m pip install --user fastapi uvicorn >/dev/null 2>&1 || {
      echo "⚠️  依赖安装失败，请手动运行：pip3 install fastapi uvicorn"; exit 1;
    }
  }
fi

# 启动
"$PYBIN" -m uvicorn app:app --host 127.0.0.1 --port "$PORT" --reload &
SERVER_PID=$!
echo $SERVER_PID > /tmp/heliostat_pid
sleep 2

echo ""
echo "✅ 已启动 (PID=$SERVER_PID)。请在浏览器打开："
echo ""
echo "    👉  http://127.0.0.1:$PORT"
echo ""
echo "🛑 停止服务：kill $SERVER_PID   或者按 Ctrl+C"
wait $SERVER_PID
