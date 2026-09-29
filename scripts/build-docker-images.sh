#!/usr/bin/env bash
# Construye las imagenes Docker principales del proyecto en el orden requerido.
set -euo pipefail

dry_run=false
no_cache=false

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            dry_run=true
            ;;
        --no-cache)
            no_cache=true
            ;;
        *)
            echo "Unknown option: $arg" >&2
            echo "Usage: $0 [--dry-run] [--no-cache]" >&2
            exit 1
            ;;
    esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

if [[ "$dry_run" != true ]] && ! command -v docker >/dev/null 2>&1; then
    echo "docker is not available in PATH. Start Docker Desktop or install Docker first." >&2
    exit 1
fi

build_image() {
    local image="$1"
    local context="$2"
    local args=(build -t "$image")

    if [[ "$no_cache" == true ]]; then
        args+=(--no-cache)
    fi
    args+=("$context")

    echo
    echo "Building $image from $context"

    if [[ "$dry_run" == true ]]; then
        printf 'docker'
        printf ' %q' "${args[@]}"
        printf '\n'
        return
    fi

    docker "${args[@]}"
}

build_image "soca-heavy:latest" "containers/soca_container"
build_image "rsfc-heavy:latest" "containers/rsfc_container"
build_image "resqui-heavy:latest" "containers/resqui_container"
build_image "rsmetacheck-bot:latest" "integrations/rsmetacheck-bot-0.6.0"
build_image "rsmetacheck-bot-conf:latest" "containers/rsmetacheck-bot_container"

echo
echo "Docker image build sequence completed."
echo "DashVERSE backend/frontend images are built separately by 'just deploy' from integrations/DashVERSE."
