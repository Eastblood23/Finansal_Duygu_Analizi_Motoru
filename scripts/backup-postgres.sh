#!/usr/bin/env bash
# Run as root. Secrets remain in PostgreSQL/rclone; never enable shell tracing.
set -Eeuo pipefail
umask 077

config=${FINANS_BACKUP_CONFIG:-/etc/finans-backup.conf}
[[ $EUID == 0 && -f $config && ! -L $config ]] || { echo 'Root and a regular configuration file are required.' >&2; exit 1; }
[[ $(stat -c %u "$config") == 0 && $(stat -c %a "$config") == 600 ]] || { echo 'Configuration must be root-owned with mode 600.' >&2; exit 1; }
# This file contains only installation settings, not credentials.
source "$config"
: "${APP_RESOURCE_ID:?}" "${BACKUP_ROOT:?}" "${RCLONE_CONFIG:?}" "${B2_BUCKET:?}"
[[ $APP_RESOURCE_ID =~ ^[a-z0-9]+$ && $B2_BUCKET =~ ^finans-b2:[a-z0-9-]+$ ]] || exit 1
[[ $BACKUP_ROOT == /* && $BACKUP_ROOT != / && $BACKUP_ROOT != *..* && ! -L $BACKUP_ROOT ]] || exit 1
for command in docker rclone jq flock sha256sum timeout; do command -v "$command" >/dev/null; done
[[ -f $RCLONE_CONFIG && ! -L $RCLONE_CONFIG && $(stat -c %u "$RCLONE_CONFIG") == 0 && $(stat -c %a "$RCLONE_CONFIG") == 600 ]] || { echo 'Protect the root rclone config with chmod 600.' >&2; exit 1; }
install -d -m 700 "$BACKUP_ROOT"
BACKUP_ROOT=$(realpath "$BACKUP_ROOT")
exec 9>"$BACKUP_ROOT/.lock"
flock -n 9 || { echo 'Another backup is already running.' >&2; exit 1; }

verifier=''
run_dir=''
success=false
finish() {
    result=$?
    trap - EXIT
    if [[ -n $verifier ]]; then docker rm -f "$verifier" >/dev/null 2>&1 || true; fi
    if [[ -n $run_dir ]]; then rm -f -- "$run_dir/database.partial" "$run_dir/download.partial"; fi
    if [[ $success != true ]]; then
        jq -n --arg time "$(date -u +%FT%TZ)" '{last_attempt_utc:$time,success:false}' >"$BACKUP_ROOT/last-attempt.json.tmp"
        mv "$BACKUP_ROOT/last-attempt.json.tmp" "$BACKUP_ROOT/last-attempt.json"
        echo 'BACKUP FAILED: see the service log; previous verified backups were preserved.' >&2
        [[ $result != 0 ]] || result=1
    fi
    exit "$result"
}
trap finish EXIT

# Select exactly one application PostgreSQL, never Coolify's own database.
mapfile -t candidates < <(docker ps --format '{{.ID}} {{.Names}}' | awk -v prefix="postgres-${APP_RESOURCE_ID}-" 'index($2,prefix)==1 {print $1}')
[[ ${#candidates[@]} == 1 ]] || { echo 'Expected exactly one running application PostgreSQL.' >&2; exit 1; }
database_container=${candidates[0]}
[[ $(docker inspect --format '{{index .Config.Labels "com.docker.compose.service"}}' "$database_container") == postgres ]] || exit 1

# Refuse a wrongly configured unencrypted destination.
remote_type=$(rclone --config "$RCLONE_CONFIG" listremotes --long | awk '$1=="finans-backup:" {print $2}')
[[ $remote_type == crypt ]] || { echo 'finans-backup must be a crypt remote.' >&2; exit 1; }
rclone_args=(--config "$RCLONE_CONFIG" --retries 3 --low-level-retries 3 --contimeout 20s --timeout 2m)
remote_bytes=$(rclone "${rclone_args[@]}" size "$B2_BUCKET" --b2-versions --json | jq -er '.bytes')
free_bytes=$(df -PB1 "$BACKUP_ROOT" | awk 'NR==2 {print $4}')
[[ $remote_bytes -lt 8000000000 && $free_bytes -gt 2000000000 ]] || { echo 'Storage safety threshold exceeded.' >&2; exit 1; }

run_name="backup-$(date -u +%Y%m%dT%H%M%SZ)-$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')"
run_dir="$BACKUP_ROOT/$run_name"
mkdir -m 700 "$run_dir"
timeout 15m docker exec "$database_container" sh -eu -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --compress=6 --no-owner --no-privileges --lock-wait-timeout=30s' >"$run_dir/database.partial"
[[ -s $run_dir/database.partial ]] || exit 1
mv "$run_dir/database.partial" "$run_dir/database.dump"
dump_bytes=$(stat -c %s "$run_dir/database.dump")
# Keep headroom below B2's first 10 GB; include all existing object versions.
[[ $((remote_bytes + dump_bytes + 1000000)) -lt 8000000000 ]] || { echo 'Remote storage budget would be exceeded.' >&2; exit 1; }

# Restore into a separate, temporary PostgreSQL container: no ports or network,
# no production volume and no writes to the application's database.
image=$(docker inspect --format '{{.Config.Image}}' "$database_container")
verifier="finans-restore-$run_name"
docker run --detach --rm --name "$verifier" --network none --cpus 0.5 --memory 512m --memory-swap 512m \
    --label finans.backup.restore-check=true \
    -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=restore_check "$image" >/dev/null
ready=false
for _ in {1..60}; do
    # The image's temporary init server accepts Unix sockets before createdb.
    # TCP becomes ready only after initialization and its final server restart.
    if docker exec "$verifier" pg_isready -h 127.0.0.1 -U postgres -d restore_check >/dev/null 2>&1; then ready=true; break; fi
    sleep 1
done
[[ $ready == true ]] || exit 1
timeout 15m docker exec -i "$verifier" pg_restore -U postgres -d restore_check --exit-on-error --single-transaction --no-owner --no-privileges <"$run_dir/database.dump"
counts=$(docker exec "$verifier" psql -X -U postgres -d restore_check -v ON_ERROR_STOP=1 -At -c \
    "SELECT json_build_object('users',(SELECT count(*) FROM public.users),'news_items',(SELECT count(*) FROM public.news_items),'portfolio_items',(SELECT count(*) FROM public.portfolio_items),'watchlists',(SELECT count(*) FROM public.watchlists));")
docker stop "$verifier" >/dev/null
verifier=''
checksum=$(sha256sum "$run_dir/database.dump" | awk '{print $1}')
jq -n --arg time "$(date -u +%FT%TZ)" --arg sha "$checksum" --argjson bytes "$dump_bytes" --argjson counts "$counts" \
    '{created_at_utc:$time,format:"PostgreSQL custom archive",sha256:$sha,size_bytes:$bytes,restore_verified:true,row_counts:$counts,scope:"Application database only; excludes roles, credentials and Coolify control plane"}' >"$run_dir/manifest.json"

rclone "${rclone_args[@]}" copyto "$run_dir/database.dump" "finans-backup:postgres/$run_name/database.dump"
rclone "${rclone_args[@]}" copyto "$run_dir/manifest.json" "finans-backup:postgres/$run_name/manifest.json"
# Verify the actual cloud copy after decryption, not only a successful upload.
rclone "${rclone_args[@]}" cat "finans-backup:postgres/$run_name/database.dump" >"$run_dir/download.partial"
[[ $(sha256sum "$run_dir/download.partial" | awk '{print $1}') == "$checksum" ]] || exit 1
rm -f -- "$run_dir/download.partial"
touch "$run_dir/upload.verified"
jq -n --arg time "$(date -u +%FT%TZ)" --arg path "finans-backup:postgres/$run_name" \
    '{last_attempt_utc:$time,success:true,remote_path:$path,restore_verified:true,cloud_round_trip_verified:true}' >"$BACKUP_ROOT/last-attempt.json.tmp"
mv "$BACKUP_ROOT/last-attempt.json.tmp" "$BACKUP_ROOT/last-attempt.json"
cp "$BACKUP_ROOT/last-attempt.json" "$BACKUP_ROOT/last-success.json"

# Remove only known files in completed local backup directories older than 7d.
# Remote expiry is handled by B2 lifecycle rules; never sync/purge the bucket.
while IFS= read -r -d '' old; do
    [[ $(basename "$old") =~ ^backup-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$ && -f $old/upload.verified && ! -L $old ]] || continue
    rm -f -- "$old/database.dump" "$old/manifest.json" "$old/upload.verified"
    rmdir -- "$old" || true
done < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +7 -print0)
success=true
echo "BACKUP OK: $run_name; restore and encrypted cloud round trip verified."
