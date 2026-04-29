#!/bin/bash

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT=$(readlink -f "${SCRIPT_DIR}/..")
BACKUP_DIR="${PROJECT_ROOT}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# Database Configs
MONGO_CONTAINER="chiwi-mongo"
MONGO_DB_NAME="chiwi"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

backup_mongo() {
    local backup_file="${BACKUP_DIR}/mongodb_${MONGO_DB_NAME}_${TIMESTAMP}.gz"
    log_message "Starting MongoDB backup for database: ${MONGO_DB_NAME}..."
    
    # Check if container is running
    if ! docker ps -q -f "name=${MONGO_CONTAINER}" | grep -q . ; then
        log_message "Error: MongoDB container '${MONGO_CONTAINER}' not found or not running!"
        return 1
    fi
    
    # Run mongodump and pipe to gzip
    # --archive without a filename writes to stdout
    if docker exec "${MONGO_CONTAINER}" mongodump --db "${MONGO_DB_NAME}" --archive --gzip > "${backup_file}"; then
        if [ ! -s "${backup_file}" ]; then
             log_message "Error: MongoDB backup produced an empty file!"
             rm -f "${backup_file}"
             return 1
        fi
        log_message "MongoDB backup successful: ${backup_file}"
        
        # Cleanup old backups
        find "${BACKUP_DIR}" -type f -name "mongodb_${MONGO_DB_NAME}_*.gz" -mtime +${RETENTION_DAYS} -exec rm {} \;
        log_message "Cleaned up backups older than ${RETENTION_DAYS} days."
    else
        log_message "Error: MongoDB backup failed!"
        rm -f "${backup_file}"
        return 1
    fi
}

main() {
    log_message "Starting ChiWi MongoDB Backup Process..."
    log_message "Project Root: ${PROJECT_ROOT}"
    
    backup_mongo
    local status=$?
    
    if [ $status -eq 0 ]; then
        log_message "Backup process completed successfully."
        exit 0
    else
        log_message "Backup process failed."
        exit 1
    fi
}

main
