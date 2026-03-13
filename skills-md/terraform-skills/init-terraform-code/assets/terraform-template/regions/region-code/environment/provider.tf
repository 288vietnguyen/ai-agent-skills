terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
      version = "~> 5.0, < 6.0.0"         # Change it depend on Organization Standard
    }
  }
}

provider "aws" {
  region = local.common.aws_region
}