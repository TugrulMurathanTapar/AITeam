param(
    [string]$ProjectRoot = $PSScriptRoot,
    [switch]$RunApplication
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

function Test-PythonVersion {
    param([string]$Executable, [string[]]$PrefixArguments = @())
    try {
        & $Executable @PrefixArguments -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Find-Python {
    $candidates = @()
    $pyLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $candidates += @{ Executable = $pyLauncher.Source; Prefix = @('-3') }
    }
    foreach ($name in @('python.exe', 'python3.exe')) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found -and $found.Source -notlike '*\Microsoft\WindowsApps\*') {
            $candidates += @{ Executable = $found.Source; Prefix = @() }
        }
    }

    foreach ($base in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
        $env:ProgramFiles
    )) {
        if ($base -and (Test-Path -LiteralPath $base)) {
            Get-ChildItem -LiteralPath $base -Directory -Filter 'Python*' -ErrorAction SilentlyContinue |
                ForEach-Object {
                    $candidate = Join-Path $_.FullName 'python.exe'
                    if (Test-Path -LiteralPath $candidate) {
                        $candidates += @{ Executable = $candidate; Prefix = @() }
                    }
                }
        }
    }

    foreach ($candidate in $candidates) {
        if (Test-PythonVersion -Executable $candidate.Executable -PrefixArguments $candidate.Prefix) {
            return $candidate
        }
    }
    return $null
}

Write-Host 'AI Orchestrator Windows kurulumu hazırlanıyor...' -ForegroundColor Cyan
$python = Find-Python
if (-not $python) {
    $winget = Get-Command 'winget.exe' -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'Python 3.10+ bulunamadı ve winget mevcut değil. Windows App Installer/winget kurup tekrar deneyin.'
    }

    Write-Host 'Python 3.12 bulunamadı; winget ile kullanıcı hesabına kuruluyor...' -ForegroundColor Yellow
    & $winget.Source install --id Python.Python.3.12 --exact --scope user --accept-source-agreements --accept-package-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) {
        throw "Python kurulumu başarısız oldu (winget çıkış kodu: $LASTEXITCODE)."
    }
    $python = Find-Python
    if (-not $python) {
        throw 'Python kurulmuş görünüyor ancak 3.10+ Python çalıştırılabilir dosyası bulunamadı. Yeni bir terminal açıp tekrar deneyin.'
    }
}

$pythonPrefix = @($python.Prefix)
$pythonVersion = & $python.Executable @pythonPrefix --version
Write-Host "Python bulundu: $pythonVersion" -ForegroundColor Green

if (-not (Test-PythonVersion -Executable $VenvPython)) {
    if (Test-Path -LiteralPath $VenvPython) {
        Write-Host 'Mevcut sanal ortamda Python 3.10+ bulunamadı; yeniden oluşturuluyor (.venv)...' -ForegroundColor Yellow
    } else {
        Write-Host 'Sanal ortam oluşturuluyor (.venv)...' -ForegroundColor Yellow
    }
    & $python.Executable @pythonPrefix -m venv --clear (Join-Path $ProjectRoot '.venv')
    if ($LASTEXITCODE -ne 0 -or -not (Test-PythonVersion -Executable $VenvPython)) {
        throw 'Sanal ortam oluşturulamadı.'
    }
}

$requirements = Join-Path $ProjectRoot 'requirements.txt'
if (Test-Path -LiteralPath $requirements) {
    Write-Host 'Python bağımlılıkları yükleniyor/güncelleniyor...' -ForegroundColor Yellow
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip güncellenemedi.' }
    & $VenvPython -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Python bağımlılıkları kurulamadı.' }
}

if ($RunApplication) {
    Write-Host 'AI Orchestrator başlatılıyor...' -ForegroundColor Green
    $env:PYTHONPATH = $ProjectRoot
    Push-Location $ProjectRoot
    try {
        & $VenvPython -c 'from ui.app import run; run()'
        if ($LASTEXITCODE -ne 0) {
            throw "Uygulama hata koduyla kapandı: $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host 'Kurulum tamamlandı. Başlatmak için launcher\run.bat dosyasını çalıştırın.' -ForegroundColor Green
}
