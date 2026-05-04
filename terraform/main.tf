# FHIR-First: Multimodal Clinical AI Backend
# Complete Terraform IaC — generated from prompt.md

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.primary_region
}

# See variables.tf for all configurable parameters
# See modules/ for individual service configurations
