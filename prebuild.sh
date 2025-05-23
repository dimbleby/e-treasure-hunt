#!/bin/bash
set -euo pipefail

UV="${HOME}/.local/bin/uv"
if [[ ! -f ${UV} ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
${UV} export --extra azure --no-dev --frozen -o requirements.txt
