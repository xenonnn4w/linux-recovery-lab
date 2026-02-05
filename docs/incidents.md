# Incident guide

For every incident preserve the baseline, failed probe, diagnostic output, repair, and recovered probe. `lab.py test` records these automatically. Elapsed times cover injection through recovery and include Docker overhead; they are not production MTTR measurements.

## Configuration

The process remains running but a dependency check returns HTTP 503. Compare `/etc/lab/config.json` against the required `message=ready` contract. Valid JSON alone does not imply valid application configuration.

## Permissions

The configuration is root-owned, and mode 0600 prevents UID 10001 from reading it. Inspect `ls -ln`, confirm the service identity in the Containerfile, and restore 0644. Do not use world-writable permissions as the repair.

## Storage

Only the 1 MiB lab tmpfs is filled. The service cannot write its health marker and reports ENOSPC. Inspect `df`, remove `/var/lib/lab/fill`, and verify a fresh write succeeds. Host disk exhaustion is not injected.

## Service

Stopping the container makes the endpoint unavailable. Inspect container state before assuming a network fault. Restart it, recreate its ephemeral configuration, and confirm HTTP 200. tmpfs contents do not survive the stop/start cycle.

## Scope

One node, four deterministic failures. This demonstrates process/container lifecycle and Linux diagnostics; it does not demonstrate fleet-scale reliability, persistent data recovery, physical repair, or systemd proficiency.
