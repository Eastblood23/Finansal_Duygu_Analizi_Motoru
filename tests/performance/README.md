# Isolated performance tests

These scripts are for disposable local benchmarking only. Never expose the benchmark
API: it deliberately disables rate limiting and adds test-only collection/resource endpoints.
The benchmark has its own Compose project/network, PostgreSQL tmpfs database and Redis.
It publishes no host ports and uses synthetic credentials/data. The existing model-cache
volume is mounted read-only; no live database volume or real API credentials are used.
Yahoo/Gemini are stubbed; FinBERT, SQL, Redis, JWT verification and password hashing are real.

PowerShell, from the repository root:

```powershell
$env:PERF_CPUS='1'
$env:PERF_MEMORY='1g'
docker compose -f tests/performance/compose.yml up -d --wait postgres redis api worker web
docker compose -f tests/performance/compose.yml run --rm --no-deps -T load python /bench/load.py --profile optimized-api1-worker1
docker compose -f tests/performance/compose.yml run --rm --no-deps -T load python /bench/extra.py --profile optimized-api1-worker1
docker compose -f tests/performance/compose.yml down
```

Historical api2cpu/api4cpu reports describe the old in-API collector. Current source always uses the separate 1 CPU / 2 GiB worker. Use unique profile/output names to preserve baseline results.
The profile quotas apply to API only. PostgreSQL has 1 CPU/768 MiB; Nginx .5 CPU/128 MiB;
Redis .5 CPU/128 MiB. This is NOT a test of a whole machine limited to 2 or 4 CPUs.
The load generator is outside those quotas, on the same host. Samples are closed-loop,
with no browser think time; concurrency is in-flight requests, not people.

On the current benchmark, expand to 100,000 news rows and test again:

```powershell
docker compose -f tests/performance/compose.yml exec -T api python /bench/scale.py
docker compose -f tests/performance/compose.yml run --rm --no-deps -T load python /bench/extra.py --profile optimized-final-100k --scale
docker compose -f tests/performance/compose.yml run --rm --no-deps -T load python /bench/soak.py
docker compose -f tests/performance/compose.yml run --rm --no-deps -T load python /bench/arrival.py
docker compose -f tests/performance/compose.yml exec -T api python /bench/queryplans.py
docker compose -f tests/performance/compose.yml down
```

Raw output goes to ignored `performance-results/`; application data is not exported.
`db_news` uses deep OFFSET scans, mostly empty and uncached; near 100,000 rows the first
few replies can contain tail data and be cached. It is a pagination worst-case test,
not a representative first-page cache miss. `dashboard` rotates through
six API reads, not a full rendered page. `chat_stub` simulates 200 ms provider wait;
it does NOT measure Gemini response time, capacity, cost or quota. The 45 s and 300 s
runs are short stability samples; they do not establish absence of memory leaks.

Acceptance targets for this assessment: read p95 <=500 ms, login p95 <=1000 ms,
non-200/transport error rate <1%. These are project evaluation targets, not guarantees.
Check p99/max separately: short NLP pauses can be hidden by aggregate p95.
Capacity must be confirmed again on the chosen VPS, with real HTTPS/WAN latency,
realistic arrival rate, representative data and controlled external-service integration.

`arrival.py` repeats 25/50/100/200 requests per second three times, 15 seconds each.
It includes generator scheduling delay and bounds outstanding requests at 200. Its
`error_pct` includes work dropped at that bound, not just backend non-200 replies.
`load.py` obtains a token using the application's real synthetic-account login before
authenticated scenarios; token setup is not included in scenario timings.
The first 180-second run with manually signed tokens had HTTP 401 responses and must
not be treated as a successful stability sample. Preserve it for diagnosis.

After load generation has stopped, fault-injection/restart checks can be run only
on the disposable project. The script validates each target's Compose project label:

```powershell
$faultCode = [IO.File]::ReadAllText((Join-Path $PWD 'tests/performance/Resilience.ps1'))
& ([scriptblock]::Create($faultCode)) -OutputFile (Join-Path $PWD 'performance-results/resilience.json')
```

Pause/unpause tests are temporary unavailability simulations, not tests of database
durability after a crash. The database is in tmpfs and must never be used for real data.
No conclusions about physical SSD performance, WAL recovery or WAN failover follow.

Note: soak.py and arrival.py use fixed output filenames; preserve existing baseline files before rerunning. Run verify_improvements.py inside the API container after scaling for cursor, aggregate and index integration checks.
