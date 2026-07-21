#!/bin/bash
# PlagSini MySQL daily backup — local + optional S3 upload.
#
# Cron suggestion (daily 02:30 MYT = 18:30 UTC):
#   30 18 * * * /opt/plagsini-ev/scripts/mysql-backup.sh >> /var/log/plagsini-backup.log 2>&1
#
# Env vars (set in /etc/default/plagsini-backup or pass inline):
#   MYSQL_PASS       — root password for charging_platform DB (required)
#   AWS_S3_BUCKET    — bucket name, e.g. plagsini-backups (optional → S3 skipped)
#   AWS_REGION       — e.g. ap-southeast-1 (defaults to ap-southeast-1)
#   LOCAL_RETAIN     — days of local backups to keep (defaults 7)
#
# Requires: docker (for mysqldump), gzip. If S3 enabled, also: aws CLI v2.
set -euo pipefail

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/mysql}"
DB="${DB:-charging_platform}"
CONTAINER="${MYSQL_CONTAINER:-charging-platform-mysql}"
LOCAL_RETAIN="${LOCAL_RETAIN:-7}"
AWS_REGION="${AWS_REGION:-ap-southeast-1}"

mkdir -p "${BACKUP_DIR}"

if [ -z "${MYSQL_PASS:-}" ]; then
    # Fall back to reading from the container's env (set by docker-compose
    # from /opt/plagsini-ev/.env). Avoids hardcoding the password here.
    MYSQL_PASS=$(docker exec "${CONTAINER}" printenv MYSQL_ROOT_PASSWORD 2>/dev/null || true)
fi

if [ -z "${MYSQL_PASS}" ]; then
    echo "[$(date -Iseconds)] FATAL: MYSQL_PASS not set and not readable from container" >&2
    exit 1
fi

FILE="${DB}_${DATE}.sql.gz"
TARGET="${BACKUP_DIR}/${FILE}"

# Dump + compress in one pipe to avoid intermediate uncompressed file.
docker exec -e MYSQL_PWD="${MYSQL_PASS}" "${CONTAINER}" \
    mysqldump --single-transaction --routines --triggers -u root "${DB}" \
    | gzip > "${TARGET}"

SIZE=$(du -sh "${TARGET}" | cut -f1)
echo "[$(date -Iseconds)] local backup OK: ${FILE} (${SIZE})"

# ── Cloud upload via rclone (default: GDrive remote 'gdrive') ───────────
# Skip if RCLONE_REMOTE is explicitly blank or rclone isn't installed.
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:PlagSiniBackups}"
if [ -n "${RCLONE_REMOTE}" ] && command -v rclone >/dev/null 2>&1; then
    # Path layout daily/YYYY/MM/<file> so a year of dumps stays browsable.
    YY=$(date +%Y); MM=$(date +%m)
    DEST="${RCLONE_REMOTE}/daily/${YY}/${MM}/"
    if rclone copy "${TARGET}" "${DEST}" --quiet; then
        echo "[$(date -Iseconds)] cloud upload OK: ${RCLONE_REMOTE}/daily/${YY}/${MM}/${FILE}"
    else
        echo "[$(date -Iseconds)] WARN: rclone upload failed for ${FILE}" >&2
    fi
fi

# ── (Legacy) Optional: upload to S3 ─────────────────────────────────────
if [ -n "${AWS_S3_BUCKET:-}" ]; then
    if ! command -v aws >/dev/null 2>&1; then
        echo "[$(date -Iseconds)] WARN: AWS_S3_BUCKET set but aws CLI not installed — skip upload" >&2
    else
        YY=$(date +%Y); MM=$(date +%m)
        S3_KEY="daily/${YY}/${MM}/${FILE}"
        aws s3 cp "${TARGET}" "s3://${AWS_S3_BUCKET}/${S3_KEY}" \
            --region "${AWS_REGION}" --storage-class STANDARD_IA --no-progress
        echo "[$(date -Iseconds)] s3 upload OK: s3://${AWS_S3_BUCKET}/${S3_KEY}"
    fi
fi

# ── Prune local backups older than LOCAL_RETAIN days ────────────────────
find "${BACKUP_DIR}" -name "${DB}_*.sql.gz" -mtime "+${LOCAL_RETAIN}" -delete
echo "[$(date -Iseconds)] local prune done (retain ${LOCAL_RETAIN}d)"
