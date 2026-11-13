# Oracle / Coolify database backups

This adds a host-side backup service. It does not change Docker Compose, deploy
the application, expose PostgreSQL, or modify application data. The existing
Windows backup script remains available for local development.

## What is protected

The application PostgreSQL schema and data (users, password hashes, news,
portfolios and watchlists). `pg_dump` takes its own consistent database snapshot
while the application runs. Counts in each manifest are from the restored
snapshot, not concurrent queries against changing production data.

Every run restores its archive into a disposable PostgreSQL container with no
network or published ports. Only after successful restore is the archive and
manifest uploaded through the `finans-backup` crypt remote. The cloud archive is
downloaded/decrypted and SHA-256 compared. This read-back consumes B2 egress.
The service writes separate last-attempt and last-success timestamps so failed
runs cannot masquerade as successful backups. A lock prevents overlapping runs.

The B2 raw bucket (including old versions) must remain below 8 GB, leaving
headroom under the currently advertised first 10 GB free. The host must have
at least 2 GB free to start. These are safeguards, not a lifetime pricing promise.
If limits are reached the job fails; alerting is therefore essential. No billing
method is required for the initial free-tier setup.

## Prerequisites

- Docker, bash, rclone, jq, util-linux, coreutils.
- Root rclone config containing `finans-b2` (bucket-scoped B2 application key)
  and `finans-backup` (`crypt`, standard filename encryption, directory name
  encryption, wrapping that bucket's `encrypted` prefix).
- Save **both crypt passwords** outside this server in a password manager.
  Losing the host config and those passwords makes recovery impossible.
- Root rclone config must be mode 600. Find its path with
  `sudo rclone config file`; never print the config or keys in chat/logs/Git.
- Verify the Coolify application's resource ID and PostgreSQL Compose service
  label; the script deliberately refuses zero or multiple matching containers.

## Install (do not enable the timer yet)

Install `scripts/backup-postgres.sh` as `/usr/local/sbin/finans-backup` (root:root,
mode 700). Copy `scripts/finans-backup.conf.example` to
`/etc/finans-backup.conf` (root:root, mode 600). Set APP_RESOURCE_ID to the
application ID shown in Coolify, and verify the root rclone config path and
bucket name. This settings file has no credentials.

Install the service and timer files into `/etc/systemd/system/` (mode 644).
Run `sudo systemctl daemon-reload`. The timer runs around 04:00–04:05
**Europe/Istanbul** daily; Persistent=true catches a missed run after startup.
This uses systemd instead of cron to provide logs, a runtime deadline and status.

## Before enabling automation

1. Configure B2 bucket lifecycle in its web console: expire files under the
   dedicated `encrypted/` prefix after the chosen retention window (30 days for
   this pilot), and permanently remove hidden/old versions after 1 day. Inspect
   the actual UI before saving; B2 retention/version semantics matter. Keep
   `hard_delete=false`. The script never syncs or purges the remote bucket.
2. Run `sudo systemctl start finans-backup.service` once, then inspect
   `sudo journalctl -u finans-backup.service -n 40 --no-pager` and
   `sudo cat /var/backups/finans/last-success.json`.
3. Confirm B2 contains encrypted objects and the live application's data remains
   accessible. A local archive listing alone is not proof of a usable backup.
4. Only after success enable `sudo systemctl enable --now finans-backup.timer`.
   Check `sudo systemctl list-timers finans-backup.timer --no-pager`.
5. Monitor last-success age (alert if older than 30 hours), service failures,
   B2 quota and free disk. No outbound alert destination has been configured by
   these files; configure it separately and test delivery.

Local completed backups are removed after seven days; incomplete/failed archives
are retained for investigation and can fill disk if failures are ignored.
Remote lifecycle expiration can remove recoverable history even if this server
is offline: retention does not replace failure alerts. To stop scheduling,
`sudo systemctl disable --now finans-backup.timer` (does not delete backups).

## Recovery

Restore the rclone configuration or recreate the same crypt remote with the
saved passwords and B2 credentials on a replacement host. List
`sudo rclone lsf finans-backup:postgres/ --dirs-only`, select a known successful
backup, download database.dump and manifest.json into a private directory and
verify the manifest's SHA-256. Restore into a **new** PostgreSQL database/container
using `pg_restore --exit-on-error --single-transaction --no-owner --no-privileges`.
Check schema and manifest counts, then point the stopped API/worker at the new
database. Never overwrite production or restore while application writes run.

## Not included / remaining work

Coolify's own database, `/data/coolify/source/.env`, project environment/API keys,
Redis, model cache and the rclone recovery configuration are not part of this
application database archive. Keep the secrets/configuration securely off-server
separately. The model cache can be downloaded again. This is a single-host
pilot, not high availability. The timer is **not installed or enabled** simply
because these files exist in Git; live B2 database backup verification remains
an installation step.
