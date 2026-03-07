#!/bin/bash
set -euo pipefail

# Install ODBC Driver 18 for SQL Server if not already present
if ! odbcinst -q -d -n "ODBC Driver 18 for SQL Server" > /dev/null 2>&1; then
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
    . /etc/os-release
    echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/${ID}/${VERSION_ID}/prod ${VERSION_CODENAME} main" > /etc/apt/sources.list.d/mssql-release.list
    apt-get update
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18
    rm -rf /var/lib/apt/lists/*
fi

exec daphne -b 0.0.0.0 treasure.asgi:application
