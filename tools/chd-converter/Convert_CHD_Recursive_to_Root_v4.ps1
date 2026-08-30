param()

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Log = Join-Path $Root "CHD_recursive_conversion_log_v4.txt"

function Log {
    param([string]$Text)
    Add-Content -LiteralPath $Log -Value $Text -Encoding UTF8
}

function Get-FreeGB {
    try {
        $driveRoot = [System.IO.Path]::GetPathRoot($Root)
        $drive = New-Object System.IO.DriveInfo($driveRoot)
        return [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
    } catch {
        return $null
    }
}

Clear-Host
@(
"============================================================"
" PS1 CHD Recursive to Root Converter v4"
" Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
" Root: $Root"
"============================================================"
) | Set-Content -LiteralPath $Log -Encoding UTF8

Write-Host "============================================================"
Write-Host "  PS1 CHD Recursive to Root Converter v4"
Write-Host "============================================================"
Write-Host
Write-Host "Safe re-run mode:"
Write-Host "  - existing complete BIN+CUE pairs are SKIPPED"
Write-Host "  - failed/missing games are RETRIED"
Write-Host "  - original CHD files are KEPT"
Write-Host "  - CHDMAN stdout/stderr are captured safely"
Write-Host

$Chdman = Join-Path $Root "chdman.exe"
if (-not (Test-Path -LiteralPath $Chdman)) {
    $cmd = Get-Command chdman.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $Chdman = $cmd.Source
    } else {
        Write-Host "ERROR: chdman.exe was not found." -ForegroundColor Red
        Read-Host "Press Enter to close"
        exit 1
    }
}

$ChdFiles = @(Get-ChildItem -LiteralPath $Root -Filter *.chd -File -Recurse -ErrorAction SilentlyContinue)

if ($ChdFiles.Count -eq 0) {
    Write-Host "No CHD files were found."
    Read-Host "Press Enter to close"
    exit 0
}

$freeGB = Get-FreeGB
if ($null -ne $freeGB) {
    Write-Host "Free space on output drive: $freeGB GB"
    Log "Initial free space: $freeGB GB"
}
Write-Host "CHD files found: $($ChdFiles.Count)"
Write-Host

$answer = Read-Host "Continue? Type YES"
if ($answer -ne "YES") {
    Write-Host "Cancelled."
    exit 0
}

$converted = 0
$skipped = 0
$failed = 0
$incompleteRemoved = 0

foreach ($file in $ChdFiles) {
    Write-Host
    Write-Host "------------------------------------------------------------"
    Write-Host "Source:"
    Write-Host "  $($file.FullName)"

    $base = $file.BaseName
    $cue = Join-Path $Root ($base + ".cue")
    $bin = Join-Path $Root ($base + ".bin")

    $cueExists = Test-Path -LiteralPath $cue
    $binExists = Test-Path -LiteralPath $bin

    if ($cueExists -and $binExists) {
        Write-Host "SKIPPED: complete BIN+CUE pair already exists." -ForegroundColor Cyan
        Log "SKIPPED EXISTING: $($file.FullName) -> $cue | $bin"
        $skipped++
        continue
    }

    if ($cueExists -xor $binExists) {
        Write-Host "Incomplete previous output found; removing it before retry." -ForegroundColor Yellow
        if ($cueExists) { Remove-Item -LiteralPath $cue -Force -ErrorAction SilentlyContinue }
        if ($binExists) { Remove-Item -LiteralPath $bin -Force -ErrorAction SilentlyContinue }
        Log "REMOVED INCOMPLETE OUTPUT: $($file.FullName)"
        $incompleteRemoved++
    }

    $freeGB = Get-FreeGB
    if ($null -ne $freeGB) {
        Write-Host "Free space before conversion: $freeGB GB"
    }

    Write-Host "Converting to:"
    Write-Host "  $cue"
    Write-Host "  $bin"

    $stdoutFile = Join-Path $env:TEMP ("chdman_out_" + [guid]::NewGuid().ToString("N") + ".txt")
    $stderrFile = Join-Path $env:TEMP ("chdman_err_" + [guid]::NewGuid().ToString("N") + ".txt")

    try {
        $argList = @(
            "extractcd",
            "-i", "`"$($file.FullName)`"",
            "-o", "`"$cue`"",
            "-ob", "`"$bin`""
        )

        $proc = Start-Process -FilePath $Chdman `
            -ArgumentList $argList `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutFile `
            -RedirectStandardError $stderrFile

        $stdout = ""
        $stderr = ""
        if (Test-Path -LiteralPath $stdoutFile) {
            $stdout = Get-Content -LiteralPath $stdoutFile -Raw -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $stderrFile) {
            $stderr = Get-Content -LiteralPath $stderrFile -Raw -ErrorAction SilentlyContinue
        }

        if ($stdout) { Write-Host $stdout.Trim() }
        if ($stderr) { Write-Host $stderr.Trim() }

        $detail = (($stdout, $stderr) | Where-Object { $_ -and $_.Trim() }) -join [Environment]::NewLine

        if ($proc.ExitCode -ne 0) {
            throw "CHDMAN exit code $($proc.ExitCode)`n$detail"
        }

        if (-not (Test-Path -LiteralPath $cue)) {
            throw "CUE file was not created.`n$detail"
        }

        if (-not (Test-Path -LiteralPath $bin)) {
            throw "BIN file was not created.`n$detail"
        }

        Write-Host "OK" -ForegroundColor Green
        Log "OK: $($file.FullName) -> $cue | $bin"
        if ($detail) { Log $detail }
        $converted++
    }
    catch {
        Write-Host "FAILED" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        Log "FAILED: $($file.FullName)"
        Log $_.Exception.Message

        if (Test-Path -LiteralPath $cue) { Remove-Item -LiteralPath $cue -Force -ErrorAction SilentlyContinue }
        if (Test-Path -LiteralPath $bin) { Remove-Item -LiteralPath $bin -Force -ErrorAction SilentlyContinue }
        $failed++
    }
    finally {
        if (Test-Path -LiteralPath $stdoutFile) { Remove-Item -LiteralPath $stdoutFile -Force -ErrorAction SilentlyContinue }
        if (Test-Path -LiteralPath $stderrFile) { Remove-Item -LiteralPath $stderrFile -Force -ErrorAction SilentlyContinue }
    }
}

Write-Host
Write-Host "============================================================"
Write-Host "  FINISHED"
Write-Host "============================================================"
Write-Host "CHD found:                  $($ChdFiles.Count)"
Write-Host "Already converted/skipped:  $skipped"
Write-Host "Converted now:              $converted"
Write-Host "Failed:                     $failed"
Write-Host "Incomplete outputs removed: $incompleteRemoved"
$freeGB = Get-FreeGB
if ($null -ne $freeGB) {
    Write-Host "Free space remaining:        $freeGB GB"
}
Write-Host
Write-Host "Log:"
Write-Host "  $Log"
Write-Host
Read-Host "Press Enter to close"
