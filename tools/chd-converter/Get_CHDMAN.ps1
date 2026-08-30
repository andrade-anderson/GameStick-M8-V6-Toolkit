$ErrorActionPreference = "Stop"

$Destination = Split-Path -Parent $MyInvocation.MyCommand.Path
$ChdmanOut = Join-Path $Destination "chdman.exe"

function Fail([string]$Message) {
    Write-Host
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

Write-Host "Destination:"
Write-Host "  $Destination"
Write-Host

if (Test-Path -LiteralPath $ChdmanOut) {
    Write-Host "chdman.exe already exists:" -ForegroundColor Yellow
    Write-Host "  $ChdmanOut"
    $answer = Read-Host "Replace it with the latest official MAME version? Type YES"
    if ($answer -ne "YES") {
        Write-Host "Cancelled. Existing chdman.exe was not changed."
        exit 0
    }
}

# Find 7-Zip.
$sevenZipCandidates = @(
    (Join-Path $env:ProgramFiles "7-Zip\7z.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "7-Zip\7z.exe")
)

$SevenZip = $null

$cmd7z = Get-Command 7z.exe -ErrorAction SilentlyContinue
if ($cmd7z) {
    $SevenZip = $cmd7z.Source
}

if (-not $SevenZip) {
    foreach ($candidate in $sevenZipCandidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $SevenZip = $candidate
            break
        }
    }
}

if (-not $SevenZip) {
    Fail "7-Zip was not found. Install 7-Zip first, then run GET_CHDMAN.bat again."
}

Write-Host "7-Zip found:"
Write-Host "  $SevenZip"
Write-Host

# Determine native architecture.
$arch = $env:PROCESSOR_ARCHITECTURE
if ($env:PROCESSOR_ARCHITEW6432) {
    $arch = $env:PROCESSOR_ARCHITEW6432
}

switch -Regex ($arch) {
    "ARM64" { $assetSuffix = "arm64"; break }
    "AMD64|x86_64" { $assetSuffix = "x64"; break }
    default { Fail "Unsupported Windows architecture: $arch" }
}

Write-Host "Windows architecture:"
Write-Host "  $arch -> MAME $assetSuffix package"
Write-Host

# Use the official mamedev/mame GitHub release API.
$headers = @{
    "User-Agent" = "GameStick-M8-V6-Toolkit-GET-CHDMAN"
    "Accept"     = "application/vnd.github+json"
}

Write-Host "Checking the latest official MAME release on GitHub..."

try {
    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/mamedev/mame/releases/latest" `
        -Headers $headers `
        -UseBasicParsing
}
catch {
    Fail "Could not query the official MAME GitHub release: $($_.Exception.Message)"
}

$assetPattern = "^mame\d+b_$assetSuffix\.exe$"
$asset = @($release.assets) | Where-Object { $_.name -match $assetPattern } | Select-Object -First 1

if (-not $asset) {
    Fail "Could not find the official Windows $assetSuffix binary package in release '$($release.tag_name)'."
}

Write-Host "Latest release:"
Write-Host "  $($release.name)"
Write-Host "Package:"
Write-Host "  $($asset.name)"
Write-Host

$tempRoot = Join-Path $env:TEMP ("get_chdman_" + [guid]::NewGuid().ToString("N"))
$tempPackage = Join-Path $tempRoot $asset.name
$tempExtract = Join-Path $tempRoot "mame"

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null

try {
    Write-Host "Downloading the official MAME package..."
    Invoke-WebRequest `
        -Uri $asset.browser_download_url `
        -Headers $headers `
        -OutFile $tempPackage `
        -UseBasicParsing

    if (-not (Test-Path -LiteralPath $tempPackage)) {
        Fail "The MAME package download did not create a file."
    }

    $downloadSize = (Get-Item -LiteralPath $tempPackage).Length
    if ($downloadSize -lt 1MB) {
        Fail "The downloaded MAME package is unexpectedly small."
    }

    Write-Host "Downloaded:"
    Write-Host ("  {0:N1} MB" -f ($downloadSize / 1MB))
    Write-Host
    Write-Host "Extracting the official package with 7-Zip..."

    & $SevenZip x $tempPackage "-o$tempExtract" -y | Out-Host

    if ($LASTEXITCODE -ne 0) {
        Fail "7-Zip could not extract the downloaded MAME package (exit code $LASTEXITCODE)."
    }

    $found = Get-ChildItem -LiteralPath $tempExtract -Filter "chdman.exe" -File -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $found) {
        Fail "The official package was extracted, but chdman.exe was not found."
    }

    # Copy via a temporary destination file first, then atomically replace.
    $staged = Join-Path $Destination "chdman.exe.new"
    Copy-Item -LiteralPath $found.FullName -Destination $staged -Force

    if (-not (Test-Path -LiteralPath $staged)) {
        Fail "Could not stage chdman.exe in the converter folder."
    }

    # Quick executable check before replacing the existing file.
    Write-Host
    Write-Host "Checking CHDMAN..."
    $versionText = @(& $staged 2>&1 | Select-Object -First 2 | ForEach-Object { $_.ToString() })
    $checkExit = $LASTEXITCODE

    # chdman without arguments may return a non-zero code while still printing its banner,
    # so validate by presence of the expected CHD manager text.
    $joined = $versionText -join " "
    if ($joined -notmatch "(?i)chdman|Compressed Hunks of Data") {
        Remove-Item -LiteralPath $staged -Force -ErrorAction SilentlyContinue
        Fail "The extracted executable did not identify itself as CHDMAN."
    }

    Move-Item -LiteralPath $staged -Destination $ChdmanOut -Force

    Write-Host
    Write-Host "SUCCESS" -ForegroundColor Green
    Write-Host "chdman.exe was copied to:"
    Write-Host "  $ChdmanOut"
    Write-Host
    Write-Host "Source:"
    Write-Host "  Official mamedev/mame GitHub release $($release.tag_name)"
    Write-Host
    Write-Host "CHDMAN banner:"
    foreach ($line in $versionText) {
        Write-Host "  $line"
    }
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
