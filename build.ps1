$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force -Path outputs/release-native | Out-Null
    Push-Location native_quantum
    try {
        go build -trimpath -o ../outputs/release-native/quantum-demon.exe .
        if ($LASTEXITCODE -ne 0) { throw 'Go kernel build failed' }
    } finally { Pop-Location }
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name LaplaceDemon --add-binary 'outputs/release-native/quantum-demon.exe;native_quantum' gui.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows application build failed' }
} finally { Pop-Location }
