@echo off
rem Starts Metro in its own window unless it is already running.
rem Used as a "Before launch" step of the Android Studio run configuration, so Run is the only button to press.

netstat -ano | findstr ":8081" | findstr "LISTENING" >nul
if %errorlevel%==0 (
  echo Metro is already running on port 8081.
  exit /b 0
)

cd /d "%~dp0.."
start "Metro - brWeather" cmd /k npm start
exit /b 0
