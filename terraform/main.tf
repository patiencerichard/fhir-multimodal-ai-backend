# FHIR Multimodal AI Backend — Complete Terraform IaC
# Generated from prompt.md

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.primary_region }

locals {
  p = var.project_name
}

# ── KMS CMK ──────────────────────────────────────────────────────────────────
resource "aws_kms_key" "main" {
  description             = "${local.p} CMK"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}
resource "aws_kms_alias" "main" {
  name          = "alias/${local.p}"
  target_key_id = aws_kms_key.main.key_id
}

# ── VPC ───────────────────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "${local.p}-vpc" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "${local.p}-private-${count.index}" }
}

data "aws_availability_zones" "available" { state = "available" }

resource "aws_security_group" "lambda" {
  name   = "${local.p}-lambda-sg"
  vpc_id = aws_vpc.main.id
  egress { from_port = 443; to_port = 443; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
}

# VPC Endpoints (no internet transit for AWS service calls)
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.primary_region}.s3"
  vpc_endpoint_type = "Gateway"
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.primary_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
}

resource "aws_vpc_endpoint" "bedrock" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.primary_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.lambda.id]
  private_dns_enabled = true
}

# ── HealthLake FHIR Datastore ─────────────────────────────────────────────────
resource "aws_healthlake_fhir_datastore" "main" {
  datastore_name        = "${local.p}-fhir"
  datastore_type_version = "R4"
  sse_configuration {
    kms_encryption_config {
      cmk_type   = "CUSTOMER_MANAGED_KMS_KEY"
      kms_key_id = aws_kms_key.main.arn
    }
  }
}

# ── S3 Buckets ────────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "audio"     { bucket = "${local.p}-audio" }
resource "aws_s3_bucket" "video"     { bucket = "${local.p}-video" }
resource "aws_s3_bucket" "knowledge" { bucket = "${local.p}-clinical-knowledge" }
resource "aws_s3_bucket" "audit"     { bucket = "${local.p}-audit-logs" }

resource "aws_s3_bucket_server_side_encryption_configuration" "audio" {
  bucket = aws_s3_bucket.audio.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "aws:kms"; kms_master_key_id = aws_kms_key.main.arn } }
}

resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    id     = "retain-${var.fhir_retention_years}yr"
    status = "Enabled"
    expiration { days = var.fhir_retention_years * 365 }
  }
}

# ── SQS FIFO Queues ───────────────────────────────────────────────────────────
resource "aws_sqs_queue" "voice" {
  name                        = "${local.p}-voice-intake.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  kms_master_key_id           = aws_kms_key.main.id
}

resource "aws_sqs_queue" "cough" {
  name                        = "${local.p}-cough-intake.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  kms_master_key_id           = aws_kms_key.main.id
}

resource "aws_sqs_queue" "sync" {
  name                        = "${local.p}-sync-queue.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  kms_master_key_id           = aws_kms_key.main.id
}

# ── Cognito ───────────────────────────────────────────────────────────────────
resource "aws_cognito_user_pool" "main" {
  name = "${local.p}-users"
  password_policy {
    minimum_length    = 12
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }
}

resource "aws_cognito_user_group" "roles" {
  for_each     = toset(["CHW_BASIC", "NURSE", "PHYSICIAN", "ADMIN"])
  name         = each.key
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_user_pool_client" "app" {
  name                                 = "${local.p}-app"
  user_pool_id                         = aws_cognito_user_pool.main.id
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "profile"]
  callback_urls                        = var.cognito_callback_urls
  supported_identity_providers         = ["COGNITO"]
  allowed_oauth_flows_user_pool_client = true
}

# ── DynamoDB Tables ───────────────────────────────────────────────────────────
resource "aws_dynamodb_table" "sessions" {
  name         = "${local.p}-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  attribute { name = "session_id"; type = "S" }
  ttl { attribute_name = "ttl"; enabled = true }
  server_side_encryption { enabled = true; kms_key_arn = aws_kms_key.main.arn }
}

resource "aws_dynamodb_table" "sync_queue" {
  name         = "${local.p}-sync-queue"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "encounter_id"
  attribute { name = "encounter_id"; type = "S" }
  attribute { name = "sync_status";  type = "S" }
  global_secondary_index {
    name            = "sync_status-index"
    hash_key        = "sync_status"
    projection_type = "ALL"
  }
  stream_enabled   = true
  stream_view_type = "NEW_IMAGE"
  server_side_encryption { enabled = true; kms_key_arn = aws_kms_key.main.arn }
}

resource "aws_dynamodb_table" "conflicts" {
  name         = "${local.p}-conflicts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "encounter_id"
  attribute { name = "encounter_id"; type = "S" }
  server_side_encryption { enabled = true; kms_key_arn = aws_kms_key.main.arn }
}

# ── IAM — Lambda execution role ───────────────────────────────────────────────
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type = "Service"; identifiers = ["lambda.amazonaws.com"] }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.p}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "lambda_inline" {
  name = "inline"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow"; Action = ["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"]; Resource = "arn:aws:logs:*:*:*" },
      { Effect = "Allow"; Action = ["s3:GetObject","s3:PutObject"]; Resource = ["${aws_s3_bucket.audio.arn}/*","${aws_s3_bucket.video.arn}/*","${aws_s3_bucket.knowledge.arn}/*"] },
      { Effect = "Allow"; Action = ["sqs:SendMessage","sqs:ReceiveMessage","sqs:DeleteMessage","sqs:GetQueueUrl"]; Resource = [aws_sqs_queue.voice.arn, aws_sqs_queue.cough.arn, aws_sqs_queue.sync.arn] },
      { Effect = "Allow"; Action = ["dynamodb:PutItem","dynamodb:GetItem","dynamodb:UpdateItem","dynamodb:Query"]; Resource = [aws_dynamodb_table.sessions.arn, aws_dynamodb_table.sync_queue.arn, "${aws_dynamodb_table.sync_queue.arn}/index/*"] },
      { Effect = "Allow"; Action = ["bedrock:InvokeModel"]; Resource = "*" },
      { Effect = "Allow"; Action = ["bedrock-agent-runtime:Retrieve"]; Resource = "*" },
      { Effect = "Allow"; Action = ["transcribe:StartTranscriptionJob","transcribe:GetTranscriptionJob"]; Resource = "*" },
      { Effect = "Allow"; Action = ["healthlake:CreateResource","healthlake:ReadResource"]; Resource = aws_healthlake_fhir_datastore.main.arn },
      { Effect = "Allow"; Action = ["kms:Decrypt","kms:GenerateDataKey"]; Resource = aws_kms_key.main.arn },
      { Effect = "Allow"; Action = ["ec2:CreateNetworkInterface","ec2:DescribeNetworkInterfaces","ec2:DeleteNetworkInterface"]; Resource = "*" }
    ]
  })
}

# ── Lambda Functions ──────────────────────────────────────────────────────────
locals {
  lambda_env = {
    HEALTHLAKE_DATASTORE_ID = aws_healthlake_fhir_datastore.main.id
    SESSION_TABLE           = aws_dynamodb_table.sessions.name
    VOCAB_BUCKET            = aws_s3_bucket.audio.bucket
    SUPPORTED_LANGUAGES     = jsonencode(var.supported_languages)
    ECS_CLUSTER             = aws_ecs_cluster.main.name
    RPPG_SERVICE            = aws_ecs_service.rppg.name
    COUGH_LAMBDA_NAME       = "${local.p}-cough-feature-extractor"
    ALERT_TOPIC_ARN         = aws_sns_topic.budget_alerts.arn
    KNOWLEDGE_BASE_ID       = aws_bedrockagent_knowledge_base.main.id
  }
}

data "archive_file" "lambda" {
  for_each    = toset(["channel_router", "transcription_orchestrator", "rppg_result_handler", "cough_feature_extractor", "clinical_reasoning", "fhir_sync", "budget_enforcer"])
  type        = "zip"
  source_file = "${path.module}/../lambda/${each.key}.py"
  output_path = "${path.module}/../lambda/${each.key}.zip"
}

resource "aws_lambda_function" "fns" {
  for_each      = toset(["channel_router", "transcription_orchestrator", "rppg_result_handler", "cough_feature_extractor", "clinical_reasoning", "fhir_sync", "budget_enforcer"])
  function_name = "${local.p}-${replace(each.key, "_", "-")}"
  role          = aws_iam_role.lambda.arn
  handler       = "${each.key}.handler"
  runtime       = "python3.11"
  filename      = data.archive_file.lambda[each.key].output_path
  source_code_hash = data.archive_file.lambda[each.key].output_base64sha256
  timeout       = 300
  reserved_concurrent_executions = each.key == "clinical_reasoning" ? 50 : -1
  environment { variables = local.lambda_env }
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
}

# S3 → channel_router trigger
resource "aws_s3_bucket_notification" "audio_trigger" {
  bucket = aws_s3_bucket.audio.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.fns["channel_router"].arn
    events              = ["s3:ObjectCreated:*"]
  }
  depends_on = [aws_lambda_permission.s3_invoke]
}

resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fns["channel_router"].function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.audio.arn
}

# DynamoDB Streams → fhir_sync trigger
resource "aws_lambda_event_source_mapping" "dynamo_sync" {
  event_source_arn  = aws_dynamodb_table.sync_queue.stream_arn
  function_name     = aws_lambda_function.fns["fhir_sync"].arn
  starting_position = "LATEST"
}

# ── ECS Fargate — rPPG ────────────────────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "${local.p}-cluster"
}

resource "aws_iam_role" "ecs_task" {
  name               = "${local.p}-ecs-task"
  assume_role_policy = jsonencode({ Version = "2012-10-17"; Statement = [{ Effect = "Allow"; Action = "sts:AssumeRole"; Principal = { Service = "ecs-tasks.amazonaws.com" } }] })
}

resource "aws_ecs_task_definition" "rppg" {
  family                   = "${local.p}-rppg"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  task_role_arn            = aws_iam_role.ecs_task.arn
  execution_role_arn       = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([{
    name      = "rppg"
    image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.primary_region}.amazonaws.com/${local.p}-rppg:latest"
    essential = true
    environment = [
      { name = "HEALTHLAKE_DATASTORE_ID"; value = aws_healthlake_fhir_datastore.main.id }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"  = "/ecs/${local.p}-rppg"
        "awslogs-region" = var.primary_region
        "awslogs-stream-prefix" = "rppg"
      }
    }
  }])
}

data "aws_caller_identity" "current" {}

resource "aws_ecs_service" "rppg" {
  name            = "${local.p}-rppg"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.rppg.arn
  desired_count   = 0
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.lambda.id]
  }
}

resource "aws_appautoscaling_target" "rppg" {
  max_capacity       = 10
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.rppg.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "rppg_cpu" {
  name               = "${local.p}-rppg-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.rppg.resource_id
  scalable_dimension = aws_appautoscaling_target.rppg.scalable_dimension
  service_namespace  = aws_appautoscaling_target.rppg.service_namespace
  target_tracking_scaling_policy_configuration {
    target_value = 70
    predefined_metric_specification { predefined_metric_type = "ECSServiceAverageCPUUtilization" }
  }
}

# ── Aurora Serverless v2 + pgvector ──────────────────────────────────────────
resource "aws_db_subnet_group" "main" {
  name       = "${local.p}-db"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_rds_cluster" "pgvector" {
  cluster_identifier     = "${local.p}-pgvector"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = "15.4"
  database_name          = "clinical_kb"
  master_username        = "admin"
  manage_master_user_password = true
  db_subnet_group_name   = aws_db_subnet_group.main.name
  kms_key_id             = aws_kms_key.main.arn
  storage_encrypted      = true
  skip_final_snapshot    = true
  serverlessv2_scaling_configuration { min_capacity = 0.5; max_capacity = 2 }
}

resource "aws_rds_cluster_instance" "pgvector" {
  cluster_identifier = aws_rds_cluster.pgvector.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.pgvector.engine
  engine_version     = aws_rds_cluster.pgvector.engine_version
}

# ── Bedrock Knowledge Base ────────────────────────────────────────────────────
resource "aws_iam_role" "bedrock_kb" {
  name               = "${local.p}-bedrock-kb"
  assume_role_policy = jsonencode({ Version = "2012-10-17"; Statement = [{ Effect = "Allow"; Action = "sts:AssumeRole"; Principal = { Service = "bedrock.amazonaws.com" } }] })
}

resource "aws_iam_role_policy" "bedrock_kb" {
  role = aws_iam_role.bedrock_kb.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow"; Action = ["s3:GetObject","s3:ListBucket"]; Resource = [aws_s3_bucket.knowledge.arn, "${aws_s3_bucket.knowledge.arn}/*"] },
      { Effect = "Allow"; Action = ["bedrock:InvokeModel"]; Resource = "*" }
    ]
  })
}

resource "aws_bedrockagent_knowledge_base" "main" {
  name     = "${local.p}-kb"
  role_arn = aws_iam_role.bedrock_kb.arn
  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.primary_region}::foundation-model/amazon.titan-embed-text-v2:0"
    }
  }
  storage_configuration {
    type = "RDS"
    rds_configuration {
      resource_arn            = aws_rds_cluster.pgvector.arn
      credentials_secret_arn  = aws_rds_cluster.pgvector.master_user_secret[0].secret_arn
      database_name           = "clinical_kb"
      table_name              = "bedrock_kb"
      field_mapping {
        primary_key_field = "id"
        vector_field      = "embedding"
        text_field        = "chunks"
        metadata_field    = "metadata"
      }
    }
  }
}

resource "aws_bedrockagent_data_source" "guidelines" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.main.id
  name              = "clinical-guidelines"
  data_source_configuration {
    type = "S3"
    s3_configuration { bucket_arn = aws_s3_bucket.knowledge.arn }
  }
  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration { max_tokens = 512; overlap_percentage = 20 }
    }
  }
}

# ── AppSync ───────────────────────────────────────────────────────────────────
resource "aws_appsync_graphql_api" "main" {
  name                = "${local.p}-api"
  authentication_type = "AMAZON_COGNITO_USER_POOLS"
  user_pool_config {
    user_pool_id   = aws_cognito_user_pool.main.id
    aws_region     = var.primary_region
    default_action = "ALLOW"
  }
  xray_enabled = true
}

# ── SNS + Budget ──────────────────────────────────────────────────────────────
resource "aws_sns_topic" "budget_alerts" {
  name              = "${local.p}-budget-alerts"
  kms_master_key_id = aws_kms_key.main.id
}

resource "aws_sns_topic_subscription" "budget_enforcer" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.fns["budget_enforcer"].arn
}

resource "aws_lambda_permission" "sns_budget" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fns["budget_enforcer"].function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.budget_alerts.arn
}

resource "aws_budgets_budget" "main" {
  name         = "${local.p}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_limit)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 90
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}

# ── WAF ───────────────────────────────────────────────────────────────────────
resource "aws_wafv2_web_acl" "main" {
  name  = "${local.p}-waf"
  scope = "REGIONAL"
  default_action { allow {} }

  rule {
    name     = "RateLimit"
    priority = 1
    action { block {} }
    statement {
      rate_based_statement {
        limit              = 100
        aggregate_key_type = "IP"
      }
    }
    visibility_config { cloudwatch_metrics_enabled = true; metric_name = "RateLimit"; sampled_requests_enabled = true }
  }

  rule {
    name     = "GeoRestrict"
    priority = 2
    action { block {} }
    statement {
      not_statement {
        statement {
          geo_match_statement { country_codes = var.waf_geo_restriction }
        }
      }
    }
    visibility_config { cloudwatch_metrics_enabled = true; metric_name = "GeoRestrict"; sampled_requests_enabled = true }
  }

  visibility_config { cloudwatch_metrics_enabled = true; metric_name = "${local.p}-waf"; sampled_requests_enabled = true }
}

# ── CloudWatch Alarms ─────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "fhir_errors" {
  alarm_name          = "${local.p}-fhir-write-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HealthLakeWriteErrors"
  namespace           = "FhirMultimodal"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_actions       = [aws_sns_topic.budget_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "rppg_duration" {
  alarm_name          = "${local.p}-rppg-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RppgTaskDurationSeconds"
  namespace           = "FhirMultimodal"
  period              = 300
  statistic           = "Average"
  threshold           = 60
  alarm_actions       = [aws_sns_topic.budget_alerts.arn]
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.p}-dashboard"
  dashboard_body = file("${path.module}/../cloudwatch-dashboard.json")
}

# ── CloudTrail ────────────────────────────────────────────────────────────────
resource "aws_cloudtrail" "main" {
  name                          = "${local.p}-trail"
  s3_bucket_name                = aws_s3_bucket.audit.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.main.arn
}

# ── Outputs ───────────────────────────────────────────────────────────────────
output "healthlake_datastore_id"  { value = aws_healthlake_fhir_datastore.main.id }
output "cognito_user_pool_id"     { value = aws_cognito_user_pool.main.id }
output "knowledge_base_id"        { value = aws_bedrockagent_knowledge_base.main.id }
output "appsync_graphql_url"      { value = aws_appsync_graphql_api.main.uris["GRAPHQL"] }
