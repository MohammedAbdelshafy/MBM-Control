@echo off
REM Start Chrome with CDP debug port 9222 for the native-Chrome YouTube publisher.
REM Uses your real profile, so your Google login works (bypasses bot detection).
setlocal
set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe
start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%LocalAppData%\Google\Chrome\User Data" --profile-directory=Default
echo Chrome started with debugging on port 9222.
endlocal
