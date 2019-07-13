#!/usr/bin/env bash
set -e
cd $(dirname  $(readlink -f $0))
docker-compose run --rm -e PROBE_MODE=1 cleanup
