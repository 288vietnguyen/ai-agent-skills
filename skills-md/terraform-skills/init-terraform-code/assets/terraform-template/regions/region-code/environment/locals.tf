locals {
  common = {
    aws_region    = "ap-southeast-1"
    aws_azs       = []

    namespace       = "org"
    name            = "ai-agent"
    environment     = "test"
    id_length_limit = 63
    account_id      = "" # Change it

    tags = {
      terraform       = true
      terraform-ws    = "" # Change it
      application     = "dso-ai-agents"
      application-id  = "dso-ai-agents"
    } 
  }

  custom_tag = {}


  network = {
    vpc_id      = ""
    subnet_ids  = []
  }

  ######################################################
  # S3 Buckets 
  ######################################################
  s3_buckets = {
    ai-agent = {
      create = true

      attributes        = ["buckets"]
      acl               = "private"
      control_object_ownership = true
      object_ownership  = "BucketOwnerEnforced"
      attach_policy     = false
    }
  }
}