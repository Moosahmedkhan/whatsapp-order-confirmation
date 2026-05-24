@echo off
title Semfee Order System
color 0A

echo ========================================
echo   SEMFEE WhatsApp Order System
echo ========================================
echo.
echo Starting all services...
echo.

:: Start webhook server in new window
start "Webhook Server" cmd /k "cd /d C:\Users\tak\Desktop\OCS && python webhook_server.py"

:: Wait 2 seconds
timeout /t 2 /nobreak >nul

:: Start ngrok in new window
start "Ngrok Tunnel" cmd /k "ngrok http 5000"

:: Wait 2 seconds
timeout /t 2 /nobreak >nul

:: Start order sender in new window
start "Order Sender" cmd /k "cd /d C:\Users\tak\Desktop\OCS && python send_orders.py"

:: Open dashboard in browser
timeout /t 3 /nobreak >nul
start "" "C:\Users\tak\Desktop\OCS\dashboard.html"

echo.
echo ========================================
echo   All services started!
echo   3 windows opened + dashboard
echo ========================================
echo.
pause
