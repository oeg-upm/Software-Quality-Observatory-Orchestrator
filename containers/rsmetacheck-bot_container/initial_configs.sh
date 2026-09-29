#!/bin/sh

echo "configuring somef..."
TOKEN="${GITHUB_API_TOKEN}"
printf "%s\n\n\n\n\n\n\n\n\n\n2000\n" "$TOKEN" | uv run somef configure

exec "$@"
