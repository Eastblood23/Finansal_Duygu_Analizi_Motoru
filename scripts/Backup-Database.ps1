[CmdletBinding()]
param(
    [string]$Container = 'finans_postgres',
    [string]$OutputDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'backups')
)

$ErrorActionPreference = 'Stop'

function Invoke-DockerChecked {
    param([string[]]$DockerArguments)
    $result = & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw "Docker operation failed: $($DockerArguments[0])" }
    return $result
}

$info = ((Invoke-DockerChecked @('inspect', $Container)) -join "`n" | ConvertFrom-Json)[0]
if (-not $info.State.Running) { throw 'PostgreSQL container is not running.' }
$config = @{}
foreach ($entry in $info.Config.Env) {
    $pair = $entry.Split('=', 2)
    if ($pair[0] -in @('POSTGRES_USER', 'POSTGRES_DB')) { $config[$pair[0]] = $pair[1] }
}
$dbUser = $config['POSTGRES_USER']
$sourceDatabase = $config['POSTGRES_DB']
if (-not $dbUser -or -not $sourceDatabase) { throw 'Database user/name could not be determined.' }

$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$unique = [guid]::NewGuid().ToString('N').Substring(0, 8)
$baseName = "finans_${stamp}_${unique}"
$testDatabase = "finans_restore_check_$unique"
if ($testDatabase -eq $sourceDatabase) { throw 'Restore database must differ from the source.' }
$containerDump = "/tmp/$baseName.dump"
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$dumpPath = Join-Path $outputRoot "$baseName.dump"
$partialPath = "$dumpPath.partial"
$manifestPath = Join-Path $outputRoot "$baseName.manifest.json"
$testCreated = $false

$countsSql = "SELECT json_build_object('users',(SELECT count(*) FROM public.users),'news_items',(SELECT count(*) FROM public.news_items),'portfolio_items',(SELECT count(*) FROM public.portfolio_items),'watchlists',(SELECT count(*) FROM public.watchlists));"
function Get-Counts {
    param([string]$DatabaseName)
    $json = Invoke-DockerChecked @('exec', $Container, 'psql', '-X', '-U', $dbUser, '-d', $DatabaseName, '-v', 'ON_ERROR_STOP=1', '-At', '-c', $countsSql)
    return (($json -join "`n") | ConvertFrom-Json)
}

try {
    $before = Get-Counts $sourceDatabase
    Invoke-DockerChecked @('exec', $Container, 'pg_dump', '-U', $dbUser, '-d', $sourceDatabase, '--format=custom', '--file', $containerDump) | Out-Null
    # docker cp preserves the binary archive; PowerShell output redirection does not.
    Invoke-DockerChecked @('cp', "${Container}:$containerDump", $partialPath) | Out-Null
    if ((Get-Item -LiteralPath $partialPath).Length -eq 0) { throw 'Backup file is empty.' }
    Move-Item -LiteralPath $partialPath -Destination $dumpPath
    # Restore the actual host-side copy, not just the original container archive.
    Invoke-DockerChecked @('cp', $dumpPath, "${Container}:$containerDump") | Out-Null
    Invoke-DockerChecked @('exec', $Container, 'pg_restore', '--list', $containerDump) | Out-Null
    Invoke-DockerChecked @('exec', $Container, 'createdb', '-U', $dbUser, '--maintenance-db', $sourceDatabase, '--template=template0', $testDatabase) | Out-Null
    $testCreated = $true
    Invoke-DockerChecked @('exec', $Container, 'pg_restore', '-U', $dbUser, '--dbname', $testDatabase, '--exit-on-error', '--single-transaction', '--no-owner', '--no-privileges', $containerDump) | Out-Null
    $restored = Get-Counts $testDatabase
    $after = Get-Counts $sourceDatabase
    foreach ($table in @('users', 'news_items', 'portfolio_items', 'watchlists')) {
        if ($before.$table -ne $after.$table) {
            throw "Source table $table changed during backup. Archive retained; retry verification during a quieter period."
        }
        if ($restored.$table -ne $after.$table) { throw "Restored row count differs for $table." }
    }
    $manifest = [ordered]@{
        created_at_utc = [DateTime]::UtcNow.ToString('o')
        source_database = $sourceDatabase
        backup_file = [System.IO.Path]::GetFileName($dumpPath)
        format = 'PostgreSQL custom archive'
        sha256 = (Get-FileHash -LiteralPath $dumpPath -Algorithm SHA256).Hash
        size_bytes = (Get-Item -LiteralPath $dumpPath).Length
        restore_verified = $true
        row_counts = $restored
        scope = 'Database schema and data; excludes cluster roles, .env and external API credentials'
    }
    $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    Write-Output "Verified backup: $dumpPath"
    Write-Output "Verification manifest: $manifestPath"
    Write-Output ($restored | ConvertTo-Json -Compress)
}
finally {
    # Only the uniquely named database created by this run may be removed.
    if ($testCreated -and $testDatabase -match '^finans_restore_check_[a-f0-9]{8}$' -and $testDatabase -ne $sourceDatabase) {
        Invoke-DockerChecked @('exec', $Container, 'dropdb', '-U', $dbUser, '--maintenance-db', $sourceDatabase, $testDatabase) | Out-Null
    }
    Invoke-DockerChecked @('exec', $Container, 'rm', '-f', '--', $containerDump) | Out-Null
}
