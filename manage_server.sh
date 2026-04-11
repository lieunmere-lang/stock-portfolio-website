#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
PID_FILE="$BACKEND_DIR/uvicorn.pid"
LOG_FILE="$BACKEND_DIR/server.log"
REQUIREMENTS_FILE="$BACKEND_DIR/requirements.txt"
HOST="0.0.0.0"
PORT="8000"
APP_MODULE="main:app"
BASE_URL="http://127.0.0.1:$PORT"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
FRONTEND_PORT="8001"
FRONTEND_URL="http://127.0.0.1:$FRONTEND_PORT"
FRONTEND_PID_FILE="$SCRIPT_DIR/frontend.pid"
FRONTEND_LOG_FILE="$SCRIPT_DIR/frontend.log"
TUNNEL_PORT="$PORT"
NGROK_BIN="$SCRIPT_DIR/ngrok"
NGROK_PID_FILE="$SCRIPT_DIR/ngrok.pid"
NGROK_LOG_FILE="$SCRIPT_DIR/ngrok.log"
NGROK_AUTHTOKEN="${NGROK_AUTHTOKEN:-$(grep -E '^NGROK_AUTHTOKEN=' "$BACKEND_DIR/.env" 2>/dev/null | cut -d'=' -f2- || true)}"

function usage() {
    cat <<EOF
Usage: $0 <command>

Commands:
  install             Create backend venv and install Python dependencies
  start               Start backend, frontend, and ngrok tunnel (if installed)
  stop                Stop backend, frontend, and tunnel
  restart             Restart backend, frontend, and tunnel
  status              Show backend and frontend server status
  start-backend       Start only the backend server
  stop-backend        Stop only the backend server
  status-backend      Show backend server status
  start-frontend      Start only the frontend static server
  stop-frontend       Stop only the frontend static server
  status-frontend     Show frontend static server status
  tunnel-start        Start ngrok tunnel for frontend port 8001
  tunnel-stop         Stop the ngrok tunnel
  tunnel-status       Show the current ngrok public URL
  sync                Trigger manual portfolio sync via API
  portfolio           Fetch current portfolio JSON from the API
  logs                Show the latest backend server log lines
  help                Show this help message

Examples:
  $0 install
  $0 start
  $0 status
  $0 sync
  $0 stop
EOF
}

function ensure_python() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "Error: python3 is not installed." >&2
        exit 1
    fi
}

function ensure_venv() {
    if [[ ! -x "$PYTHON" ]]; then
        echo "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
}

function install_deps() {
    ensure_python
    ensure_venv
    echo "Installing Python dependencies..."
    "$PIP" install --upgrade pip
    "$PIP" install -r "$REQUIREMENTS_FILE"
    echo "Dependencies installed in $VENV_DIR"
}

function server_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(<"$PID_FILE")
        if kill -0 "$pid" >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

function start_server() {
    if server_running; then
        echo "Server already running. PID=$(<"$PID_FILE")"
        return 0
    fi

    ensure_python
    ensure_venv
    echo "Starting backend server..."
    pushd "$BACKEND_DIR" >/dev/null
    nohup env PYTHONUNBUFFERED=1 "$PYTHON" -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
    echo "$!" > "$PID_FILE"
    popd >/dev/null
    echo "Server started on $BASE_URL"
    echo "Logs: $LOG_FILE"
}

function stop_server() {
    if ! server_running; then
        echo "Server is not running."
        return 0
    fi

    local pid
    pid=$(<"$PID_FILE")
    echo "Stopping backend server (PID=$pid)..."
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$PID_FILE"
    echo "Server stopped."
}

function status_server() {
    if server_running; then
        local pid
        pid=$(<"$PID_FILE")
        echo "Backend is running. PID=$pid"
        echo "URL: $BASE_URL"
    else
        echo "Backend is not running."
    fi
}

function frontend_running() {
    if [[ -f "$FRONTEND_PID_FILE" ]]; then
        local pid
        pid=$(<"$FRONTEND_PID_FILE")
        if kill -0 "$pid" >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

function start_frontend_server() {
    if frontend_running; then
        echo "Frontend server already running. PID=$(<"$FRONTEND_PID_FILE")"
        return 0
    fi

    echo "Starting frontend server..."
    pushd "$FRONTEND_DIR" >/dev/null
    nohup python3 frontend_server.py --host "$HOST" --port "$FRONTEND_PORT" > "$FRONTEND_LOG_FILE" 2>&1 &
    echo "$!" > "$FRONTEND_PID_FILE"
    popd >/dev/null
    echo "Frontend server started on $FRONTEND_URL"
    echo "Logs: $FRONTEND_LOG_FILE"
}

function stop_frontend_server() {
    if ! frontend_running; then
        echo "Frontend server is not running."
        return 0
    fi

    local pid
    pid=$(<"$FRONTEND_PID_FILE")
    echo "Stopping frontend server (PID=$pid)..."
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$FRONTEND_PID_FILE"
    echo "Frontend server stopped."
}

function status_frontend() {
    if frontend_running; then
        local pid
        pid=$(<"$FRONTEND_PID_FILE")
        echo "Frontend is running. PID=$pid"
        echo "URL: $FRONTEND_URL"
    else
        echo "Frontend is not running."
    fi
}

function start_all() {
    start_server
    if ! start_tunnel; then
        echo "Warning: ngrok tunnel was not started. Install ngrok or run './manage_server.sh tunnel-start' manually."
    fi
}

function stop_all() {
    stop_tunnel
    stop_server
}

function status_all() {
    status_server
    status_tunnel
}

function sync_portfolio() {
    echo "Triggering portfolio sync..."
    curl --fail --silent --show-error -X POST "$BASE_URL/api/sync"
    echo -e "\nSync request sent."
}

function show_portfolio() {
    echo "Fetching portfolio data..."
    curl --fail --silent --show-error "$BASE_URL/api/portfolio" | python3 -m json.tool
}

function tunnel_running() {
    if [[ -f "$NGROK_PID_FILE" ]]; then
        local pid
        pid=$(<"$NGROK_PID_FILE")
        if kill -0 "$pid" >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

function configure_ngrok_authtoken() {
    local ngrok_bin="$1"
    if [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
        return 0
    fi

    # Support both ngrok v2 and v3 authtoken commands
    "$ngrok_bin" config add-authtoken "$NGROK_AUTHTOKEN" > /dev/null 2>&1 || true
    "$ngrok_bin" authtoken "$NGROK_AUTHTOKEN" > /dev/null 2>&1 || true
}

function start_tunnel() {
    local ngrok_bin
    if [[ -x "$NGROK_BIN" ]]; then
        ngrok_bin="$NGROK_BIN"
    elif command -v ngrok >/dev/null 2>&1; then
        ngrok_bin=$(command -v ngrok)
    else
        echo "Error: ngrok is not installed. Install it from https://ngrok.com/ or place the ngrok binary in the project root."
        return 1
    fi
    if tunnel_running; then
        echo "Tunnel already running. PID=$(<"$NGROK_PID_FILE")"
        return 0
    fi
    if [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
        echo "Configuring ngrok auth token..."
        configure_ngrok_authtoken "$ngrok_bin"
    fi
    echo "Starting ngrok tunnel for frontend port $TUNNEL_PORT..."
    nohup "$ngrok_bin" http "$TUNNEL_PORT" > "$NGROK_LOG_FILE" 2>&1 &
    echo "$!" > "$NGROK_PID_FILE"
    sleep 2
    if ! tunnel_running; then
        echo "ngrok tunnel failed to start. Check $NGROK_LOG_FILE for details."
        rm -f "$NGROK_PID_FILE" >/dev/null 2>&1 || true
        return 1
    fi
    echo "Tunnel started. Use './manage_server.sh tunnel-status' to get the public URL."
}

function stop_tunnel() {
    if ! tunnel_running; then
        echo "Tunnel is not running."
        return 0
    fi
    local pid
    pid=$(<"$NGROK_PID_FILE")
    echo "Stopping ngrok tunnel (PID=$pid)..."
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$NGROK_PID_FILE"
    echo "Tunnel stopped."
}

function status_tunnel() {
    if ! tunnel_running; then
        echo "Tunnel is not running."
        return 0
    fi
    if ! command -v curl >/dev/null 2>&1; then
        echo "ngrok is running, but curl is required to query tunnel status."
        return 1
    fi
    local tunnel_info
    tunnel_info=$(curl --silent http://127.0.0.1:4040/api/tunnels || true)
    python3 - <<'PY'
import json,sys
try:
    data=json.loads(sys.stdin.read())
    for tunnel in data.get('tunnels', []):
        print(tunnel.get('public_url'))
except Exception:
    pass
PY
}

function tail_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        echo "Log file not found: $LOG_FILE"
        return 1
    fi
    tail -n 30 "$LOG_FILE"
}

case "${1:-help}" in
    install)
        install_deps
        ;;
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        start_all
        ;;
    status)
        status_all
        ;;
    start-backend)
        start_server
        ;;
    stop-backend)
        stop_server
        ;;
    status-backend)
        status_server
        ;;
    start-frontend)
        start_frontend_server
        ;;
    stop-frontend)
        stop_frontend_server
        ;;
    status-frontend)
        status_frontend
        ;;
    tunnel-start)
        start_tunnel
        ;;
    tunnel-stop)
        stop_tunnel
        ;;
    tunnel-status)
        status_tunnel
        ;;
    sync)
        sync_portfolio
        ;;
    portfolio)
        show_portfolio
        ;;
    logs)
        tail_logs
        ;;
    help|*)
        usage
        ;;
esac
