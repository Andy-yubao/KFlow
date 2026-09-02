@echo off
setlocal
pushd "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
    py -3 "%~dp0clone_test_repo.py" %*
) else (
    python "%~dp0clone_test_repo.py" %*
)
set "clone_exit_code=%ERRORLEVEL%"

echo.
if "%clone_exit_code%"=="0" (
    echo Fresh clone finished successfully.
) else (
    echo Fresh clone failed. Review the message above.
)
echo Press any key to close this window.
pause >nul

popd
exit /b %clone_exit_code%
