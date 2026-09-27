@echo off
set CGO_ENABLED=1
set CC=C:\Users\Ace\AppData\Local\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin\gcc.exe
cd /d F:\Sandbox\failure_factory\akashic_v2\tracer_pool
"C:\Program Files\Go\bin\go.exe" build -buildmode=c-shared -o tracer_pool.dll ./pkg/bridge
if %ERRORLEVEL% EQU 0 (
    echo Build successful! tracer_pool.dll created.
    dir tracer_pool.dll
) else (
    echo Build failed with error %ERRORLEVEL%
)
