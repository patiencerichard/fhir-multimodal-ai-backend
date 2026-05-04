#!/bin/bash
# Build and push rPPG container to ECR
set -e

REGION=${AWS_REGION:-us-east-1}
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO="clinical-ai-rppg"
TAG="latest"
URI="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:$TAG"

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
aws ecr describe-repositories --repository-names $REPO 2>/dev/null || aws ecr create-repository --repository-name $REPO
docker build -t $REPO .
docker tag $REPO:latest $URI
docker push $URI
echo "Pushed: $URI"
