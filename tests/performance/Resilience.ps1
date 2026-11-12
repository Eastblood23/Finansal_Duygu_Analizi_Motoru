param([Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference = 'Stop'
$targetApi = 'finans-performance-api-1'
$targets = @('finans-performance-redis-1', 'finans-performance-postgres-1', $targetApi)
foreach ($target in $targets) {
    $info = (docker inspect $target | ConvertFrom-Json)[0]
    if ($LASTEXITCODE -ne 0 -or $info.Config.Labels.'com.docker.compose.project' -ne 'finans-performance') {
        throw 'Refusing to operate outside the disposable benchmark project.'
    }
}
function Get-Probe {
    param([string]$Path = '/api/health')
    $result = docker exec $targetApi python /bench/probe.py --path $Path
    if ($LASTEXITCODE -ne 0) { throw 'Probe failed to execute' }
    return (($result -join "`n") | ConvertFrom-Json)
}
$results = @()
foreach ($target in $targets[0..1]) {
    $before = Get-Probe
    if ($before.status -ne 200) { throw 'Benchmark is not healthy before fault injection' }
    docker pause $target | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Pause failed' }
    try {
        $health = Get-Probe
        $read = Get-Probe '/api/sentiment/latest?limit=50'
    }
    finally {
        docker unpause $target | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Recovery failed: benchmark container remains paused' }
    }
    $recoveryWatch = [Diagnostics.Stopwatch]::StartNew()
    do {
        $after = Get-Probe
        if ($after.status -eq 200) { break }
        Start-Sleep -Milliseconds 200
    } while ($recoveryWatch.Elapsed.TotalSeconds -lt 15)
    $results += [ordered]@{service=$target; before=$before; unavailable_health=$health; unavailable_read=$read; recovered_health=$after; recovery_seconds=[Math]::Round($recoveryWatch.Elapsed.TotalSeconds,2)}
    if ($after.status -ne 200) { throw 'Benchmark did not recover after unpause' }
}
$watch = [Diagnostics.Stopwatch]::StartNew()
docker restart $targetApi | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Benchmark API restart failed' }
do {
    $probe = Get-Probe
    if ($probe.status -eq 200) { break }
    Start-Sleep -Milliseconds 500
} while ($watch.Elapsed.TotalSeconds -lt 60)
$results += [ordered]@{service=$targetApi; restart_ready_seconds=[Math]::Round($watch.Elapsed.TotalSeconds,2); recovered_health=$probe}
if ($probe.status -ne 200) { throw 'API did not become ready after restart' }
[IO.File]::WriteAllText([IO.Path]::GetFullPath($OutputFile), ($results | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
$results | ConvertTo-Json -Depth 6
