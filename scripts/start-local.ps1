param([int]$Port = 5000)
$ErrorActionPreference = 'Stop'
$repoDir = Split-Path $PSScriptRoot -Parent
Set-Location $repoDir
$pythonPath = Join-Path $repoDir '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonPath)) {
    if (Test-Path (Join-Path (Split-Path $repoDir -Parent) '.venv\Scripts\python.exe')) {
        $pythonPath = Join-Path (Split-Path $repoDir -Parent) '.venv\Scripts\python.exe'
    } else {
        python -m venv .venv
        & $pythonPath -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    }
}
& $pythonPath -m flask --app app db upgrade
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
$workerProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','flask','--app','app','worker') -WorkingDirectory $repoDir -WindowStyle Hidden -PassThru
try { & $pythonPath -m waitress --listen="127.0.0.1:$Port" app:app }
finally {
    Get-CimInstance Win32_Process -Filter "ParentProcessId = $($workerProcess.Id)" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'flask --app app worker' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    Stop-Process -Id $workerProcess.Id -ErrorAction SilentlyContinue
}
