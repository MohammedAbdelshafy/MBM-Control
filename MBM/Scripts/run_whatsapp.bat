@echo off
title WhatsApp Webhook Dashboard Server
cd /d "%~dp0\..\.."
echo Starting WhatsApp Webhook Dashboard Server on port 5005...

:loop
python MBM\Scripts\whatsapp_dashboard.py --port 5005
echo WhatsApp Webhook Server crashed or stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
