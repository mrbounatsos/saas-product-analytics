
#!/usr/bin/env bash
set -euo pipefail

EVENT_DIR="data/raw/events"

shopt -s nullglob
files=("$EVENT_DIR"/*.csv.gz)

if [ "${#files[@]}" -ne 24 ]; then
    echo "ERROR: Expected 24 monthly files, found ${#files[@]}"
    exit 1
fi

# Load all events through ONE PostgreSQL connection.
# The script uses process substitution to send
# decompressed CSV data directly to psql.

{
    echo '\set ON_ERROR_STOP on'
    echo 'BEGIN;'

    for file in "${files[@]}"; do
        echo "\\echo Loading $(basename "$file")..."

        printf "\\copy events (event_id, account_id, user_id, event_name, event_time, ingested_at, properties) FROM PROGRAM 'gzip -dc %s' WITH (FORMAT csv, HEADER true)\n" "$file"
    done

    echo 'COMMIT;'
} | psql -X -v ON_ERROR_STOP=1

echo "All event files loaded."
