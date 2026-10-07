@echo off
REM Start the agent-tab-driver relay on Windows.
REM First run: creates relay-config.json (asks for your Tailscale IP and an
REM optional shell token), then starts the relay with it.
setlocal
if not exist relay-config.json (
  echo First run — creating relay-config.json
  set /p CFG_HOST="This computer's Tailscale IP (run 'tailscale ip' to find it): "
  set /p CFG_TOKEN="Shell token for POST /run (Enter to disable shell access): "
  (
    echo {
    echo   "host": "%CFG_HOST%",
    echo   "port": 8765,
    echo   "token": "%CFG_TOKEN%",
    echo   "audit_log": "relay-audit.log"
    echo }
  ) > relay-config.json
  echo Wrote relay-config.json — keep it private, it may hold your token.
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 relay.py
) else (
  python relay.py
)
pause
