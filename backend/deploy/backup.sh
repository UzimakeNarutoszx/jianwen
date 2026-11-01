#!/bin/sh
set -eu
umask 077
backup_dir=/var/backups/jianwen
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
backup_file="$backup_dir/ENS_Project-$(date +%Y%m%d-%H%M%S).sql"
mysqldump --single-transaction --quick --no-tablespaces --set-gtid-purged=OFF ENS_Project > "$backup_file"
gzip "$backup_file"
gzip -t "$backup_file.gz"
