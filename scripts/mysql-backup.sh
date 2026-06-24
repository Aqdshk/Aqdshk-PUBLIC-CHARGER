#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/opt/backups/mysql
DB=charging_platform
PASS=PlagSiniRoot2025!

# Dump and compress
docker exec plagsini-mysql mysqldump -u root -p"${PASS}" "${DB}" \
  | gzip > "${BACKUP_DIR}/${DB}_${DATE}.sql.gz"

# Keep only last 7 days
find "${BACKUP_DIR}" -name '*.sql.gz' -mtime +7 -delete

echo "[$(date)] Backup done: ${DB}_${DATE}.sql.gz ($(du -sh ${BACKUP_DIR}/${DB}_${DATE}.sql.gz | cut -f1))"
