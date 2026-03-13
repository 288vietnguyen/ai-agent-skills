module "this" {
  source = "cloudposse/label/null"      # Change the source depend on the Organization Policy

  version = "0.25.0"                    # Change module's Version depend on the Organization Policy

  namespace       = local.common.namespace
  environment     = local.common.environment
  name            = local.common.name
  id_length_limit = local.common.id_length_limit
  tags            = merge(local.common.tags, local.custom_tag)
}


module "s3-buckets" {
  source = "../../../module-nonprod/s3"
  context = module.this.context

  s3_buckets = {
    ai-agents = local.s3_buckets.ai-agent
  }
}