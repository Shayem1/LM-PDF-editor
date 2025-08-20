@echo off
rem ==============================================================
rem  redlist.bat – Quick “one‑click” installer for Windows
rem --------------------------------------------------------------
rem  1. Create / activate a venv
rem  2. pip install from requirements.txt
rem  3. Ensure pdf2htmlEX and wkhtmltopdf are reachable
rem  4. If missing, try Chocolatey; otherwise ask user to install manually
rem ==============================================================
setlocal

:: --------------------------------------------------------------
:: 0️⃣ Basic sanity checks
:: --------------------------------------------------------------

echo Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo "*** ERROR: Python (3.8+) is not on your PATH ***"
    echo "Please install Python from https://www.python.org/downloads/ and add it to the system PATH."
    pause & exit /b 1
)

:: Ensure we’re in the project folder that contains requirements.txt
if not exist "requirements.txt" (
    echo.
    echo "*** ERROR: No requirements.txt found ***"
    echo "Make sure you run this script from the project root (the folder that has main.py, utils/, etc.)"
    pause & exit /b 1
)

:: --------------------------------------------------------------
:: 1️⃣ Create / activate a virtual environment
:: --------------------------------------------------------------

if not exist ".venv" (
    echo "Creating virtual environment .venv ..."
    python -m venv .venv >nul 2>&1
)
echo "Activating the virtual environment..."
call .venv\Scripts\activate.bat

:: --------------------------------------------------------------
:: 2️⃣ Upgrade pip, setuptools & wheel – they’re often out‑of‑date
:: --------------------------------------------------------------

echo "Upgrading pip / setuptools / wheel ..."
python -m pip install --upgrade pip setuptools wheel >nul 2>&1

:: --------------------------------------------------------------
:: 3️⃣ Install the Python packages listed in requirements.txt
:: --------------------------------------------------------------

echo "Installing required Python packages..."
pip install -r requirements.txt
pip install customtkinter tkinterdnd2 requests

:: --------------------------------------------------------------
:: 4️⃣ Verify external binaries are on PATH
:: --------------------------------------------------------------
:check_binaries
rem PDF to HTML converter
where pdf2htmlEX >nul 2>&1
if errorlevel 1 (
    echo.
    echo "*** pdf2htmlEX not found in your PATH ***"
    goto install_pdf2htmlex
) else (
    echo "Found pdf2htmlEX"
)

rem HTML → PDF converter
where wkhtmltopdf >nul 2>&1
if errorlevel 1 (
    echo.
    echo "*** wkhtmltopdf not found in your PATH ***"
    goto install_wkhtmltopdf
) else (
    echo "Found wkhtmltopdf"
)

:: --------------------------------------------------------------
:: All set – finish up
rem --------------------------------------------------------------

echo.
echo "==== Setup complete! ===="
echo.
echo "To activate the virtual environment again later, run:"
echo   ".venv\Scripts\activate.bat"
echo.
pause
goto :eof

:install_pdf2htmlex
call :maybe_install_choco pdf2htmlEX
goto check_binaries

:install_wkhtmltopdf
call :maybe_install_choco wkhtmltopdf
goto check_binaries

:: --------------------------------------------------------------
:: Helper sub‑routine – try Chocolatey, otherwise abort
rem --------------------------------------------------------------
:maybe_install_choco
set _pkg=%1
echo.
echo "Trying to install %_pkg% via Chocolatey..."

where choco >nul 2>&1
if errorlevel 1 (
    echo.
    echo "*** Chocolatey is not installed. ***"
    echo You can:
    echo   "1) Install Chocolatey from https://chocolatey.org/install and then re-run this script."
    echo   "2) Or download the binaries manually (see the project README for links)." 
    pause
    exit /b 1
)

rem If we get here, choco exists – attempt install
echo "Installing %_pkg% with Chocolatey ..."
choco install %_pkg% -y >nul 2>&1

:: Verify installation succeeded
where %_pkg% >nul 2>&1
if errorlevel 1 (
    echo.
    echo "*** ERROR: Failed to install %_pkg% via Chocolatey ***"
    echo "Please install it manually and re-run the script."
    pause
    exit /b 1
) else (
    echo "Successfully installed %_pkg%"
)

goto :eof
