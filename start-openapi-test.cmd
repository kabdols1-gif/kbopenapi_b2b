@echo off
setlocal

set "AIS_SCRIPT_DIR=%~dp0"
set "AIS_APP_ROOT=%AIS_SCRIPT_DIR%"

if not exist "%AIS_APP_ROOT%\frontend\package.json" (
  if exist "%AIS_SCRIPT_DIR%project\frontend\package.json" set "AIS_APP_ROOT=%AIS_SCRIPT_DIR%project"
)

if not exist "%AIS_APP_ROOT%\frontend\package.json" (
  echo Could not find frontend package.json.
  echo Expected: "%AIS_APP_ROOT%\frontend\package.json"
  exit /b 1
)

if "%AIS_OPENAPI_BACKEND_PORT%"=="" set "AIS_OPENAPI_BACKEND_PORT=8020"
if "%AIS_OPENAPI_FRONTEND_PORT%"=="" set "AIS_OPENAPI_FRONTEND_PORT=3020"
if "%AIS_OPENAPI_MODE%"=="" set "AIS_OPENAPI_MODE=development"

if /I "%~1"=="/dev" set "AIS_OPENAPI_MODE=development"
if /I "%~1"=="dev" set "AIS_OPENAPI_MODE=development"
if /I "%~1"=="/development" set "AIS_OPENAPI_MODE=development"
if /I "%~1"=="development" set "AIS_OPENAPI_MODE=development"
if /I "%~1"=="/prod" set "AIS_OPENAPI_MODE=production"
if /I "%~1"=="prod" set "AIS_OPENAPI_MODE=production"
if /I "%~1"=="/production" set "AIS_OPENAPI_MODE=production"
if /I "%~1"=="production" set "AIS_OPENAPI_MODE=production"
if /I "%AIS_OPENAPI_MODE%"=="prod" set "AIS_OPENAPI_MODE=production"
if /I "%AIS_OPENAPI_MODE%"=="real" set "AIS_OPENAPI_MODE=production"

set "AIS_RUNTIME=%AIS_APP_ROOT%\\.runtime-openapi-test"

if not exist "%AIS_RUNTIME%" mkdir "%AIS_RUNTIME%"

echo === OpenAPI Integration Test Environment ===
echo Mode: %AIS_OPENAPI_MODE%
echo App root: %AIS_APP_ROOT%
echo Frontend: http://localhost:%AIS_OPENAPI_FRONTEND_PORT%
echo Backend:  http://localhost:%AIS_OPENAPI_BACKEND_PORT%
echo.

if exist "%AIS_SCRIPT_DIR%stop-openapi-test.cmd" (
  call "%AIS_SCRIPT_DIR%stop-openapi-test.cmd" /quiet
  if errorlevel 1 (
    echo Existing process cleanup failed. Continuing with startup...
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$appRoot=$env:AIS_APP_ROOT.TrimEnd('\\');" ^
  "$runtime=$env:AIS_RUNTIME;" ^
  "$frontend=Join-Path $appRoot 'frontend';" ^
  "$backendPort=$env:AIS_OPENAPI_BACKEND_PORT;" ^
  "$frontendPort=$env:AIS_OPENAPI_FRONTEND_PORT;" ^
  "$mode=($env:AIS_OPENAPI_MODE).Trim().ToLowerInvariant();" ^
  "$backendBase=\"http://localhost:$backendPort\";" ^
  "New-Item -ItemType Directory -Force $runtime | Out-Null;" ^
  "$uv=Get-Command uv -ErrorAction SilentlyContinue;" ^
  "if (-not $uv) { throw 'uv command not found. Install uv or add it to PATH.' }" ^
  "$npm=Get-Command npm -ErrorAction SilentlyContinue;" ^
  "if (-not $npm) { throw 'npm command not found. Install Node.js/npm or add it to PATH.' }" ^
  "if (-not (Test-Path (Join-Path $frontend 'package.json'))) { throw ('frontend package.json not found: ' + $frontend) }" ^
  "if (-not (Test-Path (Join-Path $frontend 'node_modules'))) { Write-Host '[Frontend] node_modules not found, running npm install...'; Push-Location $frontend; cmd.exe /d /s /c 'npm install'; $code=$LASTEXITCODE; Pop-Location; if ($code -ne 0) { exit $code } }" ^
  "$backendOut=Join-Path $runtime 'backend.log';" ^
  "$backendErr=Join-Path $runtime 'backend.err.log';" ^
  "$frontendOut=Join-Path $runtime 'frontend.log';" ^
  "$frontendErr=Join-Path $runtime 'frontend.err.log';" ^
  "Write-Host ('[Backend] Starting on port ' + $backendPort + ' (' + $mode + ')...');" ^
  "$backendArgs=@('run','python','-m','uvicorn','backend.main:app','--host','0.0.0.0','--port',$backendPort);" ^
  "if ($mode -ne 'production') { $backendArgs += '--reload' }" ^
  "$backend=Start-Process -FilePath $uv.Source -ArgumentList $backendArgs -WorkingDirectory $appRoot -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -WindowStyle Hidden -PassThru;" ^
  "$backend.Id | Set-Content -Path (Join-Path $runtime 'backend.pid') -Encoding ascii;" ^
  "Start-Sleep -Seconds 2;" ^
  "if ($backend.HasExited) { throw ('Backend failed to start. See ' + $backendErr) }" ^
  "Write-Host ('[Frontend] Starting on port ' + $frontendPort + ' (' + $mode + ')...');" ^
  "$frontendEnv='set \"NEXT_PUBLIC_API_URL=' + $backendBase + '\" && set \"NEXT_PUBLIC_OPENAPI_TEST=1\" && set \"NEXT_PUBLIC_OPENAPI_MODE=' + $mode + '\" && ';" ^
  "$frontendCommand = if ($mode -eq 'production') { $frontendEnv + 'npm run build && npm run start -- --port ' + $frontendPort } else { $frontendEnv + 'npm run dev -- --port ' + $frontendPort };" ^
  "$frontendProc=Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/s','/c', $frontendCommand) -WorkingDirectory $frontend -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -WindowStyle Hidden -PassThru;" ^
  "$frontendProc.Id | Set-Content -Path (Join-Path $runtime 'frontend.pid') -Encoding ascii;" ^
  "Start-Sleep -Seconds 2;" ^
  "if ($frontendProc.HasExited) { throw ('Frontend failed to start. See ' + $frontendErr) }" ^
  "Write-Host ('[Backend] PID: ' + $backend.Id);" ^
  "Write-Host ('[Frontend] PID: ' + $frontendProc.Id);" ^
  "Write-Host ('[Mode] ' + $mode);" ^
  "Write-Host ('[Backend URL] ' + $backendBase);" ^
  "Write-Host ('[Frontend URL] http://localhost:' + $frontendPort);"

if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo Started.
echo Logs:
echo   %AIS_RUNTIME%\backend.log
echo   %AIS_RUNTIME%\backend.err.log
echo   %AIS_RUNTIME%\frontend.log
echo   %AIS_RUNTIME%\frontend.err.log
echo.
echo Run stop-openapi-test.cmd to stop this environment.

endlocal
