#!/usr/bin/env bash
# Shared config + helpers for the AWS deploy scripts. Source this, don't run it.
set -euo pipefail

export AWS_REGION="${AWS_REGION:-eu-north-1}"
export CLUSTER="${CLUSTER:-mri-reportgenerator}"
export NAMESPACE="${NAMESPACE:-mri}"
export IMAGE_TAG="${IMAGE_TAG:-latest}"

# Repo root = two levels up from deployment/aws.
export REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Frontend lives in a sibling worktree (feat/frontend/scaffold) until it merges to main.
export FRONTEND_DIR="${FRONTEND_DIR:-$REPO_ROOT/../frontend-worktree/frontend}"
export SAMPLE_DATA_DIR="${SAMPLE_DATA_DIR:-$REPO_ROOT/deployment/compose/sample_data}"

require() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' not installed"; exit 1; }; }

account_id() { aws sts get-caller-identity --query Account --output text; }

init_env() {
  require aws; require eksctl; require kubectl; require docker
  ACCOUNT_ID="$(account_id)"
  export ACCOUNT_ID
  export ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
  export SAMPLES_BUCKET="mri-reportgenerator-samples-${ACCOUNT_ID}"
  echo "account=$ACCOUNT_ID region=$AWS_REGION cluster=$CLUSTER"
  echo "registry=$ECR_REGISTRY"
  echo "samples_bucket=$SAMPLES_BUCKET"
}

ecr_login() {
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$ECR_REGISTRY"
}

ensure_ecr_repo() {
  local name="$1"
  aws ecr describe-repositories --repository-names "$name" --region "$AWS_REGION" >/dev/null 2>&1 \
    || aws ecr create-repository --repository-name "$name" --region "$AWS_REGION" \
         --image-scanning-configuration scanOnPush=true >/dev/null
}

# Render a templated manifest (envsubst over our known vars only) and apply it.
apply_template() {
  local file="$1"
  envsubst '${ECR_REGISTRY} ${IMAGE_TAG} ${SAMPLES_BUCKET} ${FRONTEND_ORIGIN}' < "$file" | kubectl apply -f -
}
