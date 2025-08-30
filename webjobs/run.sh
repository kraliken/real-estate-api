# #!/bin/bash
# /opt/python/3/bin/python3.13 webjob.py

#!/usr/bin/env bash
set -euo pipefail

API_URL="https://kdev-real-estate-api.azurewebsites.net/api/v1/real-estate/create"
OUT_DIR="$HOME/LogFiles/webjobs-output"
mkdir -p "$OUT_DIR"

echo "[$(date -Iseconds)] POST $API_URL"

# --- ha van kulcsod, ezt a sort kapcsold be és add hozzá a -H sort:
# AUTH_HEADER="X-Api-Key: ${JOB_API_KEY:-}"
# && a curl-hoz tedd hozzá: -H "$AUTH_HEADER"

# 3 próbálkozás, 5 mp várakozás
for attempt in 1 2 3; do
  HTTP_CODE=$(curl -sS -X POST "$API_URL" \
    -H "Accept: application/json" \
    -o "$OUT_DIR/noteWebJob-response.json" \
    -w "%{http_code}") && true

  echo "Attempt $attempt → HTTP $HTTP_CODE"
  if [[ "$HTTP_CODE" == 2* || "$HTTP_CODE" == 201 || "$HTTP_CODE" == 200 ]]; then
    echo "OK"
    exit 0
  fi

  if [[ $attempt -lt 3 ]]; then
    sleep 5
  fi
done

echo "Failed after 3 attempts (last HTTP $HTTP_CODE)"
exit 1
