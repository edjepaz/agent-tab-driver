@echo off
REM Start the agent-tab-driver relay on Windows.
REM Asks for this computer's Tailscale IP once, saves it to relay-host.txt.
setlocal
if exist relay-host.txt (
  set /p RELAY_HOST=<relay-host.txt
) else (
  set /p RELAY_HOST="Enter this computer's Tailscale IP (run 'tailscale ip' to find it): "
  echo %RELAY_HOST%>relay-host.txt
)
echo Starting relay on %RELAY_HOST%:8765 ...
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 relay.py --host %RELAY_HOST%
) else (
  python relay.py --host %RELAY_HOST%
)
pause
