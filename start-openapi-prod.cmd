@echo off
setlocal
set "AIS_OPENAPI_MODE=production"
call "%~dp0start-openapi-test.cmd" /prod
endlocal
