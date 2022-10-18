#!/bin/bash

# In this approach, we rsync to local the remote repodata directories individually for each (hardcoded) repo
# If rsync exits with success code, means there's a change, and then we purge Cloudflare

declare -a DISTS=("7" "7Server" "8/Everything" "8/Modular" "next/8/Everything" "playground/8/Everything" "testing/7" "testing/8/Everything" "testing/8/Modular" "testing/next/8/Everything")
declare -a REPOS=("SRPMS" "aarch64" "aarch64/debug" "ppc64" "ppc64/debug" "ppc64le" "ppc64le/debug" "x86_64" "x86_64/debug" "source/tree")

# get length of an array
REPOS_COUNT=${#REPOS[@]}
DISTS_COUNT=${#DISTS[@]}

for (( i=0; i<${DISTS_COUNT}; i++ )); do
  DIST="${DISTS[$i]}"
  for (( j=0; j<${REPOS_COUNT}; j++ )); do
      REPO="${REPOS[$j]}"
      echo "index i: $i, index j: $j, dist: ${DIST}, repo: ${REPO}"
      REPO="${REPOS[$j]}"
      REPO_META_DIR="/srv/www/epel.cloud/public/${DIST}/${REPO}/repodata"
      mkdir -p $REPO_META_DIR
      RSYNC_OUT=$(rsync -azi --delete rsync://mirror.yandex.ru/fedora-epel/${DIST}/${REPO}/repodata/ $REPO_META_DIR/)
      if [ $? -eq 0 ]; then
            # Success do some more work!
            if [ -n "${RSYNC_OUT}" ]; then
               echo "Purging repo ${REPO}"
               curl -X POST "https://api.cloudflare.com/client/v4/zones/XXXXXXXXX/purge_cache" \
                    -H "X-Auth-Email: YYYYYYYYYY" \
                    -H "X-Auth-Key: ZZZZZZZZZ" \
                    -H "Content-Type: application/json" \
                    --data "{\"files\":[\"https://epel.cloud/pub/epel/${DIST}/${REPO}/repodata/repomd.xml\"]}"
            fi
      fi
  done
done