#!/usr/bin/env bash
# Runs CI's ha-test job (ty, mypy, then pytest tests/ha) on Linux or in WSL.
# From Windows: wsl.exe -e bash scripts/ha-test.sh [pytest args]
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cache="${BILKATOGO_HA_CACHE:-$HOME/.cache/bilkatogo-ha}"
uv_version="0.13.5"
uv="$cache/uv/uv"

mkdir -p "$cache"

if [[ ! -x "$uv" ]] || [[ "$("$uv" --version)" != "uv $uv_version"* ]]; then
  curl -LsSf "https://astral.sh/uv/$uv_version/install.sh" \
    | env UV_INSTALL_DIR="$cache/uv" UV_NO_MODIFY_PATH=1 sh >/dev/null
fi

# lru-dict builds from source; without a system C compiler, use zig's.
if ! command -v cc >/dev/null 2>&1; then
  if [[ ! -x "$cache/zig/bin/python" ]]; then
    "$uv" venv -q --python 3.14 "$cache/zig"
    "$uv" pip install -q --python "$cache/zig/bin/python" ziglang
  fi
  cat >"$cache/zigcc" <<EOF
#!/usr/bin/env bash
args=()
for a in "\$@"; do
  case "\$a" in
    -Wl,--exclude-libs,ALL|-Wl,--build-id=sha1) ;;
    *) args+=("\$a") ;;
  esac
done
exec "$cache/zig/bin/python" -m ziglang cc "\${args[@]}"
EOF
  chmod +x "$cache/zigcc"
  export CC="$cache/zigcc" CXX="$cache/zigcc"
fi

# Work on a copy in the Linux filesystem: /mnt/c is slow and its .venv is Windows-only.
rsync -a --delete \
  --exclude .git --exclude .venv --exclude __pycache__ \
  --exclude .ruff_cache --exclude .pytest_cache --exclude .claude \
  "$repo/" "$cache/src/"
cd "$cache/src"

export UV_PROJECT_ENVIRONMENT="$cache/venv" UV_PYTHON=3.14.9
"$uv" sync -q --locked --no-default-groups --group ha
"$uv" run --no-sync ty check custom_components tests/ha
"$uv" run --no-sync mypy --strict --explicit-package-bases custom_components/bilkatogo
"$uv" run --no-sync pytest -p no:cacheprovider tests/ha "$@"
