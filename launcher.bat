@echo off
rem ------------------------------------------------------------
rem  launch.bat   –  activate the virtual‑environment & run main.py
rem ------------------------------------------------------------

REM 1️⃣  Make this folder the working directory
pushd "%~dp0"

REM ------------------------------------------------------------------
REM 2️⃣  Activate the venv (change "venv" to whatever your folder is called)
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual‑environment...
    call venv\Scripts\activate.bat
) else (
    echo.
    echo   ERROR:  Virtual environment not found!
    echo   Run 'redlist.bat' first (it will create the venv and install deps).
    pause
    popd
    exit /b 1
)

REM ------------------------------------------------------------------
rem 3️⃣  Verify that Python is now reachable (it should be via the env)
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR:  Python not found after activating venv.
    pause
    popd
    exit /b 1
)

REM ------------------------------------------------------------------
rem 4️⃣  Run your main script.  %* forwards any arguments you typed after the batch file name.
echo.
echo Running: python main.py %*
python main.py %*

REM ------------------------------------------------------------------
rem 5️⃣  Return to original directory (optional but tidy)
popd

rem ------------------------------------------------------------
rem   End of launch.bat
