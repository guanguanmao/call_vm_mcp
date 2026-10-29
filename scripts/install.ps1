param(
    [string]$Python = 'python',
    [string]$WheelDirectory = ''
)
$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$serviceVenv = Join-Path $serviceRoot '.venv'
if (-not (Test-Path -LiteralPath (Join-Path $serviceVenv 'Scripts\python.exe'))) {
    & $Python -m venv $serviceVenv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment' }
}
$servicePython = Join-Path $serviceVenv 'Scripts\python.exe'
$installArgs = @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', (Join-Path $serviceRoot 'requirements.lock.txt'))
if ($WheelDirectory) { $installArgs += @('--no-index', '--find-links', $WheelDirectory) }
& $servicePython @installArgs
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $servicePython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed' }
$localInventory = Join-Path $serviceRoot 'config.local.json'
if (-not (Test-Path -LiteralPath $localInventory)) {
    Copy-Item -LiteralPath (Join-Path $serviceRoot 'configs\machines.example.json') -Destination $localInventory
    Write-Output "Edit the VMware executable and VMX paths in: $localInventory"
}
Write-Output "Ready. Launcher: $servicePython $serviceRoot\serve.py"
