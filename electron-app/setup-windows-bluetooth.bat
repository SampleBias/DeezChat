@echo off
setlocal

:: Set console colors
set "green=[92m"
set "red=[91m"
set "yellow=[93m"
set "blue=[94m"
set "cyan=[96m"
set "white=[97m"
set "reset=[0m"

echo %cyan%DeezChat Windows Bluetooth Setup%reset%
echo ========================================

:: Check administrator privileges
net session >nul 2>&1
if errorlevel 1 (
    echo %red%❌ ERROR: Administrator privileges required!%reset%
    echo Please run this script as Administrator.
    echo.
    echo Right-click on this script and select "Run as administrator"
    pause
    exit /b 1
)

echo %green%✅ Running with administrator privileges%reset%
echo.

:: Check Python installation
echo %blue%🔍 Checking Python installation...%reset%

set "python_cmd="
for %%p in (python3 python py python.exe) do (
    %%p --version >nul 2>&1
    if !errorlevel (
        echo %green%✅ Found Python: %%p%reset%
        set "python_cmd=%%p"
        goto :python_found
    )
)

:python_not_found
echo %red%❌ ERROR: Python 3.6+ not found!%reset%
echo.
echo Please install Python 3.6+ from:
echo • https://www.python.org/downloads/
echo • Microsoft Store: https://www.microsoft.com/p/python-3
echo • winget install --id Python.Python.3
echo.
pause
exit /b 1

:python_found
echo %blue%  Python version:%reset%
%python_cmd% --version

:: Check if DeezChat is importable
echo %blue%🔍 Checking DeezChat module...%reset%

%python_cmd% -c "import deezchat; print('DEEZCHAT_OK')" >nul 2>&1
if errorlevel 1 (
    echo %red%❌ ERROR: DeezChat module not found!%reset%
    echo.
    echo Please install DeezChat first by running the Electron app
    echo and clicking "Install DeezChat CLI" button.
    echo.
    echo Alternatively, install manually:
    echo • pip install -e .
    echo • From the repository directory
    echo.
    pause
    exit /b 1
)

echo %green%✅ DeezChat module found and importable%reset%
echo.

:: Check Windows Bluetooth
echo %blue%🔍 Checking Windows Bluetooth status...%reset%

set "bluetooth_found=0"

:: Method 1: Check Bluetooth service
sc query bluetooth >nul 2>&1
if !errorlevel (
    for /f "tokens=2 delims==" %%i in ('sc query bluetooth ^| find "STATE"') do (
        if /i "%%i"=="RUNNING" (
            echo %green%✅ Bluetooth service is running%reset%
            set "bluetooth_found=1"
            goto :bluetooth_check_done
        )
    )
)

:: Method 2: Check via PowerShell
powershell -Command "Get-PnpDevice -Class Bluetooth" -ErrorAction SilentlyContinue | findstr /i "Bluetooth" >nul 2>&1
if !errorlevel (
    echo %green%✅ Bluetooth devices found via PnP%reset%
    set "bluetooth_found=1"
)

:bluetooth_check_done
if %bluetooth_found%==0 (
    echo %yellow%⚠️  WARNING: No Bluetooth service or devices detected%reset%
    echo.
    echo This could mean:
    echo • Bluetooth is disabled in Windows Settings
    echo • Bluetooth hardware is not present
    echo • Bluetooth drivers are not installed
    echo.
    echo Please check Windows Settings ^> Bluetooth ^& other devices
    echo.
)

:: Create DeezChat launcher script
echo %blue%🚀 Creating DeezChat launcher...%reset%

set "launcher_path=%USERPROFILE%\DeezChat\deezchat-launch.bat"

if not exist "%USERPROFILE%\DeezChat" mkdir "%USERPROFILE%\DeezChat"

(
echo @echo off
echo %cyan%DeezChat Launcher%reset%
echo ==================
echo Starting DeezChat...
echo.

:: Check if Python is available
for %%p in (python3 python py python.exe) do (
    where %%p >nul 2>&1
    if !errorlevel (
        set "python_cmd=%%p"
        goto :python_in_launcher
    )
)

:python_in_launcher
if defined python_cmd (
    %python_cmd% -m deezchat %*
) else (
    echo %red%❌ ERROR: Python not found in PATH%reset%
    echo Please install Python and ensure it's in your PATH
    echo.
    pause
)

) > "%launcher_path%"

echo %green%✅ Launcher created: %launcher_path%%reset%
echo.

:: Create PowerShell launcher script
set "ps_launcher_path=%USERPROFILE%\DeezChat\deezchat-launch.ps1"

(
echo %cyan%DeezChat PowerShell Launcher%reset%
echo ===============================
echo

:: Try to find Python
$pythonPath = & where.exe python 3.0
$pythonPath = & where.exe python 2.7
$pythonPath = & where.exe python
$pythonPath = & where.exe py

if ($pythonPath) {
    $pythonCmd = $pythonPath[0]
} elseif ($python27Path) {
    $pythonCmd = $python27Path[0]
} elseif ($pythonPath) {
    $pythonCmd = $pythonPath[0]
} else {
    Write-Host "❌ ERROR: Python not found" -ForegroundColor Red
    Write-Host "Please install Python 3.6+ from:" -ForegroundColor Yellow
    Write-Host "• https://www.python.org/downloads/" -ForegroundColor Cyan
    Read-Host "Press any key to exit..." -ForegroundColor White
    Read-Host
    exit 1
}

Write-Host "✅ Found Python: $pythonCmd" -ForegroundColor Green
Write-Host "🚀 Starting DeezChat..." -ForegroundColor Cyan
Set-Location $PSScriptRoot

try {
    Start-Process $pythonCmd -ArgumentList "-m", "deezchat" -Wait -NoNewWindow -ErrorAction Stop
    Write-Host "✅ DeezChat started successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to start DeezChat: $_" -ForegroundColor Red
    Write-Host "Press any key to exit..." -ForegroundColor Yellow
    Read-Host
}
) > "%ps_launcher_path%"

echo %green%✅ PowerShell launcher created: %ps_launcher_path%%reset%
echo.

:: Set up Windows Firewall for DeezChat
echo %blue%🔥 Setting up Windows Firewall for DeezChat...%reset%

echo Checking if firewall is available...
netsh advfirewall firewall show rule name="DeezChat" >nul 2>&1
if errorlevel 1 (
    echo %blue%📋 Windows Firewall found, checking rules...%reset%
    
    :: Add outbound rules for DeezChat
    netsh advfirewall firewall add rule name="DeezChat Outbound TCP" dir=out action=allow protocol=TCP localport=any remoteport=any enable=yes description="DeezChat outbound TCP" >nul 2>&1
    netsh advfirewall firewall add rule name="DeezChat Outbound UDP" dir=out action=allow protocol=UDP localport=any remoteport=any enable=yes description="DeezChat outbound UDP" >nul 2>&1
    
    echo %green%✅ Added outbound firewall rules for DeezChat%reset%
    
    :: Add inbound rule for potential future features
    netsh advfirewall firewall add rule name="DeezChat Bluetooth" dir=in action=allow protocol=TCP localport=any remoteport=any program="%~dp0\deezchat\deezchat.exe" enable=yes description="DeezChat Bluetooth access" >nul 2>&1
    echo %green%✅ Added Bluetooth firewall rule for DeezChat%reset%
    
    echo %green%✅ Windows Firewall configured for DeezChat%reset%
) else (
    echo %yellow%⚠️  Windows Firewall not accessible%reset%
    echo Firewall rules may need to be added manually
)

:: Create Windows Service registration (optional)
echo %blue%🔧 Creating Windows Service registration...%reset%

sc create "DeezChat" binpath= "\"%USERPROFILE%\DeezChat\deezchat-launch.bat\"" start=auto 2>nul
if errorlevel 1 (
    echo %yellow%⚠️  Could not create Windows service (may need administrator)%reset%
) else
    echo %green%✅ DeezChat Windows service created%reset%
    echo %blue%   You can manage the service with:%reset%
    echo %cyan%   sc start DeezChat%reset%
    echo %cyan%   sc stop DeezChat%reset%
    echo %cyan%   sc delete DeezChat%reset%
)

echo.
echo %green%✅ Windows setup completed!%reset%
echo.
echo %cyan%📱 Next Steps for DeezChat on Windows:%reset%
echo.
echo "1. Start the Electron DeezChat application"
echo "2. Click 'Start DeezChat' button in the app"
echo "3. Grant Bluetooth permissions when prompted by Windows"
echo "4. The app will scan for BitChat peers automatically"
echo "5. Use the terminal interface to interact with discovered peers"
echo.
echo %blue%📋 Files created for you:%reset%
echo.
echo "   • Batch launcher: %launcher_path%"
echo "   • PowerShell launcher: %ps_launcher_path%"
echo "   • Windows service: DeezChat"
echo.
echo %yellow%🔧 Bluetooth Troubleshooting:%reset%
echo.
echo "If DeezChat cannot find Bluetooth devices:"
echo " • Open Windows Settings ^> Bluetooth ^& other devices"
echo " • Turn on Bluetooth and make device discoverable"
echo " • Check if device is paired with other Bluetooth devices"
echo " • Restart Bluetooth service: net stop bluetooth / net start bluetooth"
echo " • Update Bluetooth drivers from manufacturer website"
echo "   • Install Windows updates (may include Bluetooth improvements)"
echo.
echo %green%🎉 Setup complete! Launch DeezChat Electron app now.%reset%
echo.
pause