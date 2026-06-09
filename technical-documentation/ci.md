# CI / GitHub Actions

Two workflows run on every push/PR (`.github/workflows/`):
- **ci.yml** — `test` (pytest: unit + integration + golden; e2e auto-skips without `EEP_BASE_URL`) →
  `build-images` (builds the eep/measurements/reporting images) → `push-ecr` (**main only**, gated on secrets).
- **mlops.yml** — the validation/promotion gate (`python -m mlops.validate`), fails the build on a
  golden/threshold regression; uploads the MLflow DB as an artifact.

## Enabling the ECR image push (optional)
The `push-ecr` job only runs on `main` and needs three repo secrets. Two ways to provide creds:

### Option A — access keys (simplest)
Add these as **GitHub repo secrets** (Settings → Secrets and variables → Actions → New repository secret),
using the same `mri-deploy` IAM user already configured locally:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` = `eu-north-1`

CLI equivalent (run from the repo, `gh` authenticated):
```bash
gh secret set AWS_REGION            --body "eu-north-1"
gh secret set AWS_ACCESS_KEY_ID     --body "$(aws configure get aws_access_key_id)"
gh secret set AWS_SECRET_ACCESS_KEY --body "$(aws configure get aws_secret_access_key)"
```

### Option B — OIDC (no long-lived keys, preferred for real projects)
Create an IAM role trusting GitHub's OIDC provider (`token.actions.githubusercontent.com`) scoped to this
repo, grant it ECR push, and swap the `configure-aws-credentials` step to `role-to-assume:
arn:aws:iam::<acct>:role/<role>` (no access-key secrets). See the AWS "Configuring OpenID Connect in
AWS" guide.

## Notes
- Secrets are **never** committed; they live only in GitHub's encrypted store (or `~/.aws` locally).
- Until secrets are set, `push-ecr` is skipped (not failed) — `test` + `build-images` still gate every PR.
- Local deploy doesn't need any of this: `deployment/aws/02-deploy-backend.sh` pushes to ECR using your
  local `~/.aws` creds.
