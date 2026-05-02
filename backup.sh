#!/bin/bash

# Discord Bot data backup script.
# ASCII-only output keeps VPS consoles readable even when UTF-8 is not configured.

set -e

export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_DIR="backups"
DATA_DIR="data"
MAX_BACKUPS=10

print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        print_message "$BLUE" "[INFO] Created backup directory: $BACKUP_DIR"
    fi
}

generate_backup_name() {
    local timestamp
    timestamp=$(date +"%Y%m%d_%H%M%S")
    echo "dc_bot_backup_${timestamp}.tar.gz"
}

perform_backup() {
    local backup_file="$BACKUP_DIR/$(generate_backup_name)"

    print_message "$BLUE" "[INFO] Starting data backup..."
    print_message "$BLUE" "[INFO] Data directory: $DATA_DIR"
    print_message "$BLUE" "[INFO] Backup file: $backup_file"

    if [ ! -d "$DATA_DIR" ]; then
        print_message "$YELLOW" "[WARN] Data directory not found: $DATA_DIR"
        return 1
    fi

    tar -czf "$backup_file" -C . "$DATA_DIR" 2>/dev/null

    if [ $? -eq 0 ]; then
        print_message "$GREEN" "[OK] Backup complete: $backup_file"
        local size
        size=$(du -h "$backup_file" | cut -f1)
        print_message "$BLUE" "[INFO] Backup size: $size"
        return 0
    fi

    print_message "$RED" "[ERROR] Backup failed"
    return 1
}

cleanup_old_backups() {
    print_message "$BLUE" "[INFO] Cleaning old backups..."

    local backup_files
    backup_files=($(ls -t "$BACKUP_DIR"/dc_bot_backup_*.tar.gz 2>/dev/null || true))

    if [ ${#backup_files[@]} -gt $MAX_BACKUPS ]; then
        local files_to_delete
        files_to_delete=${backup_files[@]:$MAX_BACKUPS}

        for file in $files_to_delete; do
            print_message "$YELLOW" "[INFO] Removing old backup: $(basename "$file")"
            rm -f "$file"
        done

        print_message "$GREEN" "[OK] Cleanup complete. Keeping latest $MAX_BACKUPS backups"
    else
        print_message "$BLUE" "[INFO] Backup count: ${#backup_files[@]} (limit: $MAX_BACKUPS)"
    fi
}

list_backups() {
    print_message "$BLUE" "[INFO] Backup files:"
    echo

    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
        print_message "$YELLOW" "[WARN] No backup files found"
        return
    fi

    local backup_files
    backup_files=($(ls -t "$BACKUP_DIR"/dc_bot_backup_*.tar.gz 2>/dev/null || true))

    if [ ${#backup_files[@]} -eq 0 ]; then
        print_message "$YELLOW" "[WARN] No backup files found"
        return
    fi

    printf "%-35s %-15s %-20s\n" "Filename" "Size" "Created"
    echo "--------------------------------------------------------------------------"

    for file in "${backup_files[@]}"; do
        local filename size created_at
        filename=$(basename "$file")
        size=$(du -h "$file" | cut -f1)
        created_at=$(stat -c %y "$file" | cut -d' ' -f1,2 | cut -d'.' -f1)
        printf "%-35s %-15s %-20s\n" "$filename" "$size" "$created_at"
    done
}

restore_backup() {
    local backup_file="$1"

    if [ -z "$backup_file" ]; then
        print_message "$RED" "[ERROR] Specify a backup file to restore"
        echo "Usage: $0 restore <backup_file>"
        return 1
    fi

    if [ ! -f "$backup_file" ]; then
        print_message "$RED" "[ERROR] Backup file not found: $backup_file"
        return 1
    fi

    print_message "$YELLOW" "[WARN] Restoring backup: $backup_file"
    print_message "$YELLOW" "[WARN] This will overwrite the current data directory"
    read -p "Continue? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_message "$BLUE" "[INFO] Restoring backup..."

        if command -v docker-compose &> /dev/null; then
            print_message "$BLUE" "[INFO] Stopping Discord Bot..."
            docker-compose down 2>/dev/null || true
        fi

        if [ -d "$DATA_DIR" ]; then
            local current_backup
            current_backup="backup_before_restore_$(date +%Y%m%d_%H%M%S).tar.gz"
            print_message "$BLUE" "[INFO] Backing up current data: $current_backup"
            tar -czf "$current_backup" -C . "$DATA_DIR" 2>/dev/null || true
        fi

        rm -rf "$DATA_DIR"
        tar -xzf "$backup_file" -C .

        if [ $? -eq 0 ]; then
            print_message "$GREEN" "[OK] Restore complete"
            print_message "$BLUE" "[INFO] You can now restart Discord Bot"
        else
            print_message "$RED" "[ERROR] Restore failed"
            return 1
        fi
    else
        print_message "$BLUE" "[INFO] Restore cancelled"
    fi
}

show_help() {
    echo "Discord Bot data backup script"
    echo
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  backup    Back up data"
    echo "  list      List backups"
    echo "  restore   Restore a backup"
    echo "  cleanup   Remove old backups"
    echo "  help      Show this help"
    echo
    echo "Examples:"
    echo "  $0 backup"
    echo "  $0 list"
    echo "  $0 restore backup_file.tar.gz"
    echo "  $0 cleanup"
    echo
}

main() {
    case "${1:-help}" in
        "backup")
            create_backup_dir
            perform_backup
            cleanup_old_backups
            ;;
        "list")
            list_backups
            ;;
        "restore")
            restore_backup "$2"
            ;;
        "cleanup")
            create_backup_dir
            cleanup_old_backups
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

main "$@"
