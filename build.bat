@echo off
REM ---- Build "PDF Toolkit" as a Windows desktop app ----
REM Put this file, requirements.txt and pdf_toolkit.py in the same folder.
REM Optional: put an icon named icon.ico there too.
REM
REM This builds inside a clean virtual environment (.venv) so PyInstaller does NOT
REM pull in unrelated big packages (torch, numpy, etc.) from your global Python.

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

if not exist .venv (
  echo Creating clean virtual environment...
  python -m venv .venv || goto :error
)
set PY=.venv\Scripts\python.exe

%PY% -m pip install --upgrade pip || goto :error
%PY% -m pip install -r requirements.txt || goto :error

REM --- Tell Tcl/Tk where Python's files are (fixes "Can't find a usable init.tcl" in a venv) ---
for /f "delims=" %%i in ('%PY% -c "import sys;print(sys.base_prefix)"') do set BASE=%%i
if exist "%BASE%\tcl\tcl8.6\init.tcl" (
  set "TCL_LIBRARY=%BASE%\tcl\tcl8.6"
  set "TK_LIBRARY=%BASE%\tcl\tk8.6"
) else (
  echo.
  echo ERROR: Tcl/Tk was not found in your Python installation at:
  echo   %BASE%
  echo Fix: open the Windows Settings, Apps, Python 3.13, Modify, Modify,
  echo and make sure "tcl/tk and IDLE" is ticked. Then run this again.
  goto :error
)

set ICON=
if exist icon.ico set ICON=--icon icon.ico

%PY% -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name "PDF Toolkit" %ICON% ^
  --collect-all customtkinter ^
  --collect-all tkinterdnd2 ^
  --exclude-module torch --exclude-module torchvision --exclude-module torchaudio ^
  --exclude-module numba --exclude-module llvmlite --exclude-module numpy ^
  --exclude-module scipy --exclude-module pandas --exclude-module matplotlib ^
  --exclude-module tensorflow --exclude-module sklearn --exclude-module cv2 ^
  pdf_toolkit.py || goto :error

echo.
echo Done! Your app is in:  dist\PDF Toolkit\PDF Toolkit.exe
echo Next: compile installer.iss with Inno Setup to make the Setup.exe
pause
exit /b 0

:error
echo.
echo Build failed - see the messages above.
pause
exit /b 1
