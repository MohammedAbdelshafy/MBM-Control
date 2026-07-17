@echo off
echo ============================================
echo  MBM Pipeline - Install Scheduled Task
echo ============================================
echo.
echo This must be run AS ADMINISTRATOR to work.
echo Right-click this file and select "Run as administrator"
echo.
pause
echo.
echo Creating scheduled task (every 4 hours, 6x/day)...
schtasks /Create /SC DAILY /TN "MBM-Pipeline-Runner" /TR "powershell.exe -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File \"C:\Users\omare\OneDrive\Desktop\AI\MBM\Scripts\pipeline_runner.ps1\"" /ST 00:00 /RI 240 /DU 9999:00 /F /RL HIGHEST
echo.
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: Task created!
    echo.
    schtasks /Run /TN "MBM-Pipeline-Runner"
    echo Pipeline started!
) else (
    echo FAILED: Could not create task. Try running as Administrator.
)
echo.
pause
