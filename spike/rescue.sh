#!/usr/bin/env bash
# spike/rescue.sh - T12.1 step 0 (docs/plans/T12.1-pipeline.md): pack the restored cache/ (the 17 Nov catalog of S12.0,
# Actions cache spike-catalog-v1) and encrypt it for one recipient, the certificate spike/rescue-cert.pem, whose private
# key exists only on Martin's machine. Only ciphertext leaves the job.
# openssl cms -encrypt with a recipient certificate (hybrid: random AES-256 key, wrapped with RSA); docs: openssl-cms(1),
# https://docs.openssl.org/3.0/man1/openssl-cms/
# The run log is public: this script prints file names, sizes and SHA-256 only, never a line of the catalog.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/say.sh"

if [ ! -d cache/raw ]; then
    say "Catalog rescue" "cache/raw after actions/cache/restore" "no cache/raw: the cache was not restored" "check the restore step"
    exit 1
fi

files=0; bytes=0
while read -r f; do
    n=$(stat -c %s "$f")
    printf '  %s  %s bytes  sha256 %s\n' "$f" "$n" "$(sha256sum "$f" | cut -d' ' -f1)"
    files=$((files + 1)); bytes=$((bytes + n))
done < <(find cache -type f | sort)

mkdir -p rescue
tar -cf rescue/catalog.tar cache
openssl cms -encrypt -binary -aes-256-cbc -outform DER -in rescue/catalog.tar -out rescue/catalog.tar.cms "$HERE/rescue-cert.pem"
rm rescue/catalog.tar
enc=$(stat -c %s rescue/catalog.tar.cms)
sha=$(sha256sum rescue/catalog.tar.cms | cut -d' ' -f1)
num rescue.files "$files"; num rescue.bytes "$bytes"; num rescue.encrypted.bytes "$enc"; num rescue.encrypted.sha256 "$sha"

say "Catalog rescue" \
    "cache/ restored from spike-catalog-v1, packed and encrypted for spike/rescue-cert.pem (openssl cms, AES-256-CBC)" \
    "$files files, $bytes bytes; ciphertext $enc bytes, SHA-256 $sha" \
    "download the artifact, decrypt locally, then delete the artifact"
