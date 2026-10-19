# Deployment and recovery

## Backend

The production workflow uploads an archive and managed environment payload, then
[`run_remote_deploy.sh`](../../deploy/run_remote_deploy.sh) starts
[`activate_release.sh`](../../deploy/activate_release.sh) as a systemd service.
The coordinator owns preparation, writer quiescence, migrations, activation,
health checks and guarded rollback. Its stdin is null and output goes to the
journal. SSH starts and observes it; losing SSH does not cancel deployment.

Each attempt uses `<commit SHA>-<GitHub run ID>-<run attempt>` as its deployment ID.
Only one coordinator may hold `/opt/flama/deploy.lock`. Status is written atomically
to `/opt/flama/deployments/<deployment ID>.status` and includes the phase:
`preparing`, `quiescing`, `migrating`, `activating`, or `health`.

After a lost connection or Actions timeout, reconnect and inspect the same attempt:

```bash
cat /opt/flama/deployments/<deployment-ID>.status
systemctl status flama-deploy-<deployment-ID>.service
journalctl -u flama-deploy-<deployment-ID>.service --no-pager
journalctl -u flama-db-migrate-<commit-SHA>.service --no-pager
```

`running` means observation is incomplete; `succeeded health` means public-facing
services passed loopback health and the Study consumer passed readiness. A failed
or killed unit requires inspection even if a stale status says `running`. Check
public API/Connect health separately after deployment. Failure keeps staged env,
rollback env and payload files for recovery; these contain secrets and must stay
root-readable only. Successful deployment cleans them up.

Before retrying a failed attempt, confirm that its coordinator and migration units
have both stopped. A migration child is a separate systemd unit. Do not kill a
coordinator to cancel a migration, start a second migration over it, or infer DB
state from the SSH/Actions exit code.

Rollback checks must pass before restoring previous code or environment. After
Field ID contraction, a release without the canonical `field-id.v1` runtime cannot
be restarted against that database. Inspect Alembic head, the cutover manifest,
selected release and preserved env files. Finish activation with compatible code,
or use a separately verified backup restore procedure. The coordinator does not
automatically activate code after a failed migration.

## Frontend

Production is Cloudflare **Workers**, worker `flama-frontend1001`, custom domain
`flama.vn`. The Workers Builds root is `/frontend`; build command is `npm run build`
and deploy command is `npx wrangler deploy`. The latter resolves the exact local
Wrangler dependency installed from the lockfile. It must not auto-configure Vite
or install packages during deployment.

[`frontend/wrangler.jsonc`](../../frontend/wrangler.jsonc) owns the static `dist`
directory and SPA fallback. Node is pinned in `frontend/.node-version` to the CI
version. Keep the build variable `VITE_API_BASE_URL=https://api.flama.vn/api/`.
Credentials belong in the deployment environment, never in frontend source or
`VITE_*` variables.

```bash
cd frontend
npm ci
npm run build
npm run deploy:check
# With production build variables and Cloudflare credentials configured:
npm run deploy
```

CI runs the Wrangler dry run after building. Check `/`, a SPA route such as
`/login`, entry JS/CSS assets, `https://api.flama.vn/api/health` and
`https://connect.flama.vn/healthz` after publishing.

Cloudflare's [build image documentation](https://developers.cloudflare.com/workers/ci-cd/builds/build-image/)
describes Node version files; its [SPA routing documentation](https://developers.cloudflare.com/workers/static-assets/routing/single-page-application/)
describes the asset fallback.

See the [2026-10-19 incident report](incidents/2026-10-19_DEPLOY_SSH_CLOUDFLARE_OUTAGE.md)
for the failure evidence and completed recovery.
