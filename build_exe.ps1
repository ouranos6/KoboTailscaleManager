$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python312 = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
if (-not (Test-Path -LiteralPath $python312)) {
  Write-Host 'Python 3.12 avec Tcl/Tk est requis pour compiler cet EXE.' -ForegroundColor Red
  Write-Host 'Installation: winget install --id Python.Python.3.12 --exact --scope user'
  exit 1
}

$venv = Join-Path $PSScriptRoot '.venv312'
if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts\python.exe'))) {
  & $python312 -m venv $venv
}
$venvPython = Join-Path $venv 'Scripts\python.exe'
$venvPyInstaller = Join-Path $venv 'Scripts\pyinstaller.exe'

# Refuse a build which would silently exclude tkinter and create an unusable EXE.
& $venvPython -c "import tkinter; tkinter.Tcl()"
& $venvPython -m pip install --upgrade pip pyinstaller
$assetArgs = @()
if (Test-Path (Join-Path $PSScriptRoot 'assets')) {
  $assetArgs = @('--add-data', 'assets;assets')
}
& $venvPyInstaller --noconfirm --clean --onefile --windowed --name KoboTailscaleManager @assetArgs KoboTailscaleManager.pyw
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller a echoue avec le code $LASTEXITCODE."
}
Write-Host ''
Write-Host 'EXE cree :' -ForegroundColor Green
Write-Host (Join-Path $PSScriptRoot 'dist\KoboTailscaleManager.exe')
