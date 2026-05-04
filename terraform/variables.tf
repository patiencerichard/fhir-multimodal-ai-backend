variable "project_name" {
  description = "Project identifier used in resource naming"
  type        = string
  default     = "clinical-ai"
}

variable "primary_region" {
  description = "Primary AWS region (must support HealthLake)"
  type        = string
  default     = "us-east-1"
}

variable "dr_region" {
  description = "DR failover region (must support HealthLake)"
  type        = string
  default     = "eu-west-2"
}

variable "country_code" {
  description = "ISO country code for patient ID URI (e.g., tz, ke, bd)"
  type        = string
}

variable "supported_languages" {
  description = "List of Amazon Transcribe language codes"
  type        = list(string)
  default     = ["sw-TZ", "en-ZA"]
}

variable "monthly_budget_limit" {
  description = "Hard budget limit in USD"
  type        = number
  default     = 300
}

variable "cognito_callback_urls" {
  description = "Cognito OAuth callback URLs"
  type        = list(string)
  default     = ["http://localhost:3000/callback"]
}

variable "waf_geo_restriction" {
  description = "ISO country codes allowed through WAF"
  type        = list(string)
  default     = ["TZ", "KE", "UG", "RW", "BI"]
}

variable "fhir_retention_years" {
  description = "Audit log retention in years (per local data law)"
  type        = number
  default     = 7
}
