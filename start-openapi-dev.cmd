@echo off
setlocal
set "AIS_OPENAPI_MODE=development"
call "%~dp0start-openapi-test.cmd" /dev
endlocal
