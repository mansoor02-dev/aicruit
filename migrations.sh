#!/bin/bash

# Configuration
CONTAINER_NAME="docker-postgres-1"
DB_USER="admin"
DB_NAME="aicruit"
MIGRATIONS_DIR="./database/migrations"

# Loop through all .sql files in the migrations directory
for file in "$MIGRATIONS_DIR"/*.sql; do
    if [ -f "$file" ]; then
        echo "Applying migration: $file..."
        
        # Pipe the file content into the docker exec command
        cat "$file" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"
        
        # Check if the last command succeeded
        if [ $? -eq 0 ]; then
            echo "Successfully applied $file"
        else
            echo "Error applying $file. Stopping."
            exit 1
        fi
    fi
done

echo "All migrations completed."