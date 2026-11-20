#!/usr/bin/env bash
# The weekly copy's encryption, and the drill that proves it opens — AG9 (DS50-04).
#
#   backup-age.sh encrypt <dir> <recipient-file> <out>   tar + gzip <dir>, encrypt it to <out>
#   backup-age.sh roundtrip <dir> [<recipient-file>]     prove that copy opens again
#
# `encrypt` is the one command the Backup workflow encrypts with. `roundtrip` runs that same
# command with a throwaway key pair made for the occasion, decrypts the result and compares it
# with <dir>, file by file; given the real recipient file it also checks age accepts it. So the
# tooling is proved end to end without the real private key, which only the owner holds and
# which never reaches a runner. The monthly drill runs it on the real copy; CI runs it on a
# small sample every pull request. Needs `age` and `age-keygen` on the PATH.
set -euo pipefail

encrypt() {
  local dir=$1 recipients=$2 out=$3
  tar -C "$dir" -czf - . | age -R "$recipients" -o "$out"
}

roundtrip() {
  local dir=$1 recipients=${2:-}
  local work
  work=$(mktemp -d)
  # shellcheck disable=SC2064 # expanded now: $work is local and gone by exit
  trap "rm -rf '$work'" EXIT
  age-keygen -o "$work/key" 2>/dev/null
  age-keygen -y "$work/key" > "$work/recipient"
  encrypt "$dir" "$work/recipient" "$work/copy.tar.gz.age"
  mkdir "$work/opened"
  age -d -i "$work/key" "$work/copy.tar.gz.age" | tar -C "$work/opened" -xzf -
  if ! diff -r "$dir" "$work/opened" > "$work/diff"; then
    echo "::error::The copy did not come back as it went in:"
    head -20 "$work/diff"
    exit 1
  fi
  if [ -n "$recipients" ]; then
    printf 'drill' | age -R "$recipients" > /dev/null
  fi
  local files
  files=$(find "$work/opened" -type f | wc -l | tr -d ' ')
  echo "Round trip with a throwaway key: ${files} files encrypted, decrypted and identical."
}

case "${1:-}" in
  encrypt) encrypt "$2" "$3" "$4" ;;
  roundtrip) roundtrip "$2" "${3:-}" ;;
  *)
    echo "usage: $0 encrypt <dir> <recipient-file> <out> | roundtrip <dir> [<recipient-file>]" >&2
    exit 2
    ;;
esac
