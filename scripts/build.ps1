param([ValidateSet('exe', 'msi')][string]$Target = 'exe')

$AppVersion = '2.0.0'
$WixVersion = '5.0.2'
$ErrorActionPreference = 'Stop'

$Root      = Split-Path -Parent $PSScriptRoot
$SrcDir    = Join-Path $Root 'src'
$IconFile  = Join-Path $SrcDir 'assets\tandem.ico'
$Installer = Join-Path $Root 'installer'
$BuildDir  = Join-Path $Root 'build'
$DistDir   = Join-Path $Root 'dist'
Set-Location $Root
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'

function Step($text) { Write-Host "`n=== $text" -ForegroundColor Cyan }


function Update-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Install-WithWinget([string]$Id, [string]$Name, [string]$Override = '') {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$Name не найден, а winget недоступен. Установите «Установщик приложений» (App Installer) из Microsoft Store или поставьте $Name вручную."
    }
    Write-Host "$Name не найден — устанавливаю через winget ($Id)..." -ForegroundColor Yellow
    $wingetArgs = @('install', '--id', $Id, '--exact', '--silent',
                    '--accept-package-agreements', '--accept-source-agreements')
    if ($Override) { $wingetArgs += @('--override', $Override) }
    & winget @wingetArgs
    Update-Path
}

function Test-Python([string]$Exe, [string[]]$Prefix = @()) {
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $Exe @Prefix -c "import sys, platform, tkinter; print(sys.executable); print(platform.python_version()); print(platform.architecture()[0]); print('%d%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -ne 0 -or $out.Count -lt 4) { return $null }
        if ($out[2] -ne '64bit' -or [version]$out[1] -lt [version]'3.9') { return $null }
        return [pscustomobject]@{ Exe = $out[0]; Version = $out[1]; Short = $out[3] }
    } catch {
        return $null
    }
}

function Find-Python {
    $candidates = @(@{ Exe = 'python'; Prefix = @() }, @{ Exe = 'py'; Prefix = @('-3') })
    foreach ($pattern in @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe'),
                           (Join-Path $env:ProgramFiles 'Python3*\python.exe'))) {
        Get-ChildItem $pattern -ErrorAction SilentlyContinue |
            ForEach-Object { $candidates += @{ Exe = $_.FullName; Prefix = @() } }
    }
    foreach ($c in $candidates) {
        if (Get-Command $c.Exe -ErrorAction SilentlyContinue) {
            $found = Test-Python $c.Exe $c.Prefix
            if ($found) { return $found }
        }
    }
    return $null
}

function Find-Iscc {
    return @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

function Find-Dotnet {
    $ErrorActionPreference = 'Continue'
    foreach ($exe in @('dotnet', (Join-Path $env:ProgramFiles 'dotnet\dotnet.exe'))) {
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $sdks = & $exe --list-sdks 2>$null
        if ($sdks | Where-Object { $_ -match '^(\d+)\.' -and [int]$Matches[1] -ge 6 }) { return $exe }
    }
    return $null
}

try {
    Step 'Python'
    $py = Find-Python
    if (-not $py) {
        Install-WithWinget 'Python.Python.3.13' 'Python' '/quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_test=0'
        $py = Find-Python
        if (-not $py) { throw 'Python не удалось установить автоматически. Установите Python 3.9+ (64-бит) с python.org и запустите сборку ещё раз.' }
    }
    $version, $short = $py.Version, $py.Short
    Write-Host "Python $version ($($py.Exe))"

    $cache = Join-Path $BuildDir 'cache'
    $stage = Join-Path $BuildDir 'stage'
    $pyDir = Join-Path $stage 'python'
    $appDir = Join-Path $stage 'app'
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
    New-Item -ItemType Directory -Force $cache, $pyDir, $appDir | Out-Null

    Step "Встраиваемый Python $version"
    $zip = Join-Path $cache "python-$version-embed-amd64.zip"
    if (-not (Test-Path $zip)) {
        $url = "https://www.python.org/ftp/python/$version/python-$version-embed-amd64.zip"
        Write-Host "Скачивание $url"
        Invoke-WebRequest -Uri $url -OutFile "$zip.part" -UseBasicParsing
        Move-Item "$zip.part" $zip -Force
    }
    Expand-Archive -Path $zip -DestinationPath $pyDir -Force

    Step 'Добавление tkinter (во встраиваемом Python его нет)'
    & $py.Exe (Join-Path $PSScriptRoot 'collect_tkinter.py') $pyDir
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось скопировать tkinter (подробности выше).' }
    Get-ChildItem $pyDir -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force

    $pth = Get-ChildItem $pyDir -Filter 'python*._pth' | Select-Object -First 1
    @("python$short.zip", '.', 'Lib', '..\app') | Set-Content -Path $pth.FullName -Encoding Ascii

    Step 'Файлы программы'
    Get-ChildItem $SrcDir -Filter '*.py' -File | Copy-Item -Destination $appDir
    New-Item -ItemType Directory -Force (Join-Path $appDir 'assets') | Out-Null
    Copy-Item $IconFile (Join-Path $appDir 'assets')

    Step 'Проверка: встроенный Python загружает программу и Tk'
    & (Join-Path $pyDir 'python.exe') -c "import app, mirror, tray, system, autostart, settings, tkinter; root = tkinter.Tk(); root.withdraw(); root.update(); print('Tk', root.tk.call('info', 'patchlevel')); root.destroy()"
    if ($LASTEXITCODE -ne 0) { throw 'Встроенный Python не смог загрузить программу (ошибка выше).' }
    Get-ChildItem $stage -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force

    if ($Target -eq 'msi') {
        Step '.NET SDK и WiX Toolset'
        $dotnet = Find-Dotnet
        if (-not $dotnet) {
            Install-WithWinget 'Microsoft.DotNet.SDK.8' '.NET SDK 8'
            $dotnet = Find-Dotnet
            if (-not $dotnet) { throw '.NET SDK не удалось установить автоматически. Установите .NET SDK 8 с https://dotnet.microsoft.com/download и запустите сборку ещё раз.' }
        }
        Write-Host ".NET SDK: $(& $dotnet --version)"
        $wix = Join-Path $env:USERPROFILE '.dotnet\tools\wix.exe'
        $installed = (Test-Path $wix) -and ((& $wix --version) -like "$WixVersion*")
        if ($installed) {
            Write-Host "WiX $WixVersion уже установлен"
        } else {
            Write-Host "Установка WiX $WixVersion..." -ForegroundColor Yellow
            if (Test-Path $wix) { & $dotnet tool uninstall --global wix | Out-Null }
            & $dotnet tool install --global wix --version $WixVersion
            if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить WiX Toolset.' }
        }
        & $wix extension add -g "WixToolset.UI.wixext/$WixVersion"
        if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить расширение WiX UI.' }

        Step 'Сборка MSI'
        New-Item -ItemType Directory -Force $DistDir | Out-Null
        & $wix build (Join-Path $Installer 'installer.wxs') -arch x64 -culture ru-RU -ext WixToolset.UI.wixext `
            -d "AppVersion=$AppVersion" -d "StageDir=$stage" -d "IconFile=$IconFile" `
            -o (Join-Path $DistDir 'Tandem-Setup.msi')
        if ($LASTEXITCODE -ne 0) { throw 'WiX завершился с ошибкой (подробности выше).' }
        Write-Host "`nГотово: dist\Tandem-Setup.msi — этот файл можно передавать и устанавливать." -ForegroundColor Green
    } else {
        Step 'Inno Setup'
        $iscc = Find-Iscc
        if (-not $iscc) {
            Install-WithWinget 'JRSoftware.InnoSetup' 'Inno Setup 6'
            $iscc = Find-Iscc
            if (-not $iscc) { throw 'Inno Setup не удалось установить автоматически. Установите его с https://jrsoftware.org/isdl.php и запустите сборку ещё раз.' }
        }
        Write-Host "Inno Setup: $iscc"

        Step 'Сборка установщика'
        & $iscc /Q "/DAppVersion=$AppVersion" "/DStageDir=$stage" "/DIconFile=$IconFile" "/DOutDir=$DistDir" `
            (Join-Path $Installer 'installer.iss')
        if ($LASTEXITCODE -ne 0) { throw 'Inno Setup завершился с ошибкой (подробности выше).' }
        Write-Host "`nГотово: dist\Tandem-Setup.exe — этот файл можно передавать и устанавливать." -ForegroundColor Green
    }
    exit 0
} catch {
    Write-Host "`nОШИБКА: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
