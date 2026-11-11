@echo off
rem Starts Metro in its own window unless it is already running.
rem Called automatically by debug builds (see android/app/build.gradle, task startMetro), so Run is the only button to press.

netstat -ano | findstr ":8081" | findstr "LISTENING" >nul
if %errorlevel%==0 (
  echo Metro is already running on port 8081.
  exit /b 0
)

rem Android Studio may have been opened before Node.js was installed, so make sure npm is reachable
set "PATH=%PATH%;%ProgramFiles%\nodejs"

cd /d "%~dp0.."
start "Metro - brWeather" cmd /k npm start
exit /b 0
