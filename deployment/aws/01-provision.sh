#!/usr/bin/env bash
# Phase 1 — provision the EKS cluster, ECR repos, and the samples S3 bucket.
# Idempotent: safe to re-run. Takes ~15-20 min (mostly EKS control plane + nodes).
#   ./deployment/aws/01-provision.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"
init_env

echo "==> [1/3] EKS cluster ($CLUSTER)"
if eksctl get cluster --name "$CLUSTER" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "    cluster exists — skipping create"
else
  eksctl create cluster -f "$HERE/cluster.yaml"
fi
aws eks update-kubeconfig --name "$CLUSTER" --region "$AWS_REGION"

echo "==> [2/3] ECR repositories"
for repo in mri-eep mri-measurements mri-reporting mri-frontend; do
  ensure_ecr_repo "$repo"
  echo "    ok: $repo"
done

echo "==> [3/3] Samples S3 bucket ($SAMPLES_BUCKET)"
if aws s3api head-bucket --bucket "$SAMPLES_BUCKET" 2>/dev/null; then
  echo "    bucket exists"
else
  if [ "$AWS_REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$SAMPLES_BUCKET" --region "$AWS_REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$SAMPLES_BUCKET" --region "$AWS_REGION" \
      --create-bucket-configuration LocationConstraint="$AWS_REGION" >/dev/null
  fi
  aws s3api put-public-access-block --bucket "$SAMPLES_BUCKET" \
    --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
fi
echo "    uploading sample viewer data (gitignored, never in an image)"
aws s3 sync "$SAMPLE_DATA_DIR/" "s3://$SAMPLES_BUCKET/" \
  --exclude "*" --include "*.nii.gz" --include "segmentation.zip" --only-show-errors
aws s3 ls "s3://$SAMPLES_BUCKET/"

kubectl apply -f "$HERE/../k8s/namespace.yaml"
echo "==> Provision complete. Next: ./deployment/aws/02-deploy-backend.sh"
