################################################################################################
# MODULE: AMAZON SIMPLE STORAGE SERVICE (Amazon S3)
################################################################################################

module "s3-label" {
  source = "cloudposse/label/null" # Change the source depend on the Organization Policy
  version = "0.25.0"               # Change module's Version depend on the Organization Policy

  for_each = var.s3_buckets

  enabled     = each.value.enabled
  context     = each.value.context
  tags        = each.value.context.tags
  attributes  = each.value.attributes
}

module "s3-bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"         # Change the source depend on the Organization Policy
  version = "5.10.0"                                      # Change module's Version depend on the Organization Policy

  for_each      = {for k, v in var.s3_buckets : k => v if module.s3-label[k].enabled}
  create_bucket = module.s3-label[each.key].enabled
  bucket        = module.s3-label[each.key].id
  tags          = module.s3-label[each.key].tags

  acceleration_status                                 = each.value.acceleration_status
  access_log_delivery_policy_source_accounts          = each.value.access_log_delivery_policy_source_accounts
  access_log_delivery_policy_source_buckets           = each.value.access_log_delivery_policy_source_buckets
  access_log_delivery_policy_source_organizations     = each.value.access_log_delivery_policy_source_organizations
  acl                                                 = each.value.acl
  allowed_kms_key_arn                                 = each.value.allowed_kms_key_arn
  analytics_configuration                             = each.value.analytics_configuration
  analytics_self_source_destination                   = each.value.analytics_self_source_destination
  analytics_source_account_id                         = each.value.analytics_source_account_id
  analytics_source_bucket_arn                         = each.value.analytics_source_bucket_arn
  attach_access_log_delivery_policy                   = each.value.attach_access_log_delivery_policy
  attach_analytics_destination_policy                 = each.value.attach_analytics_destination_policy
  attach_cloudtrail_log_delivery_policy               = each.value.attach_cloudtrail_log_delivery_policy
  attach_deny_incorrect_encryption_headers            = each.value.attach_deny_incorrect_encryption_headers
  attach_deny_incorrect_kms_key_sse                   = each.value.attach_deny_incorrect_kms_key_sse
  attach_deny_insecure_transport_policy               = each.value.attach_deny_insecure_transport_policy
  attach_deny_ssec_encrypted_object_uploads           = each.value.attach_deny_ssec_encrypted_object_uploads
  attach_deny_unencrypted_object_uploads              = each.value.attach_deny_unencrypted_object_uploads
  attach_elb_log_delivery_policy                      = each.value.attach_elb_log_delivery_policy
  attach_inventory_destination_policy                 = each.value.attach_inventory_destination_policy
  attach_lb_log_delivery_policy                       = each.value.attach_lb_log_delivery_policy
  attach_policy                                       = each.value.attach_policy
  attach_public_policy                                = each.value.attach_public_policy
  attach_require_latest_tls_policy                    = each.value.attach_require_latest_tls_policy
  attach_waf_log_delivery_policy                      = each.value.attach_waf_log_delivery_policy
  availability_zone_id                                = each.value.availability_zone_id
  block_public_acls                                   = each.value.block_public_acls
  block_public_policy                                 = each.value.block_public_policy
  bucket_prefix                                       = each.value.bucket_prefix
  control_object_ownership                            = each.value.control_object_ownership
  cors_rule                                           = each.value.cors_rule
  create_metadata_configuration                       = each.value.create_metadata_configuration
  data_redundancy                                     = each.value.data_redundancy
  expected_bucket_owner                               = each.value.expected_bucket_owner
  force_destroy                                       = each.value.force_destroy
  grant                                               = each.value.grant
  ignore_public_acls                                  = each.value.ignore_public_acls
  intelligent_tiering                                 = each.value.intelligent_tiering
  inventory_configuration                             = each.value.inventory_configuration
  inventory_self_source_destination                   = each.value.inventory_self_source_destination
  inventory_source_account_id                         = each.value.inventory_source_account_id
  inventory_source_bucket_arn                         = each.value.inventory_source_bucket_arn
  is_directory_bucket                                 = each.value.is_directory_bucket
  lb_log_delivery_policy_source_organizations         = each.value.lb_log_delivery_policy_source_organizations
  lifecycle_rule                                      = each.value.lifecycle_rule
  location_type                                       = each.value.location_type
  logging                                             = each.value.logging
  metadata_encryption_configuration                   = each.value.metadata_encryption_configuration
  metadata_inventory_table_configuration_state        = each.value.metadata_inventory_table_configuration_state
  metadata_journal_table_record_expiration            = each.value.metadata_journal_table_record_expiration
  metadata_journal_table_record_expiration_days       = each.value.metadata_journal_table_record_expiration_days
  metric_configuration                                = each.value.metric_configuration
  object_lock_configuration                           = each.value.object_lock_configuration
  object_lock_enabled                                 = each.value.object_lock_enabled
  object_ownership                                    = each.value.object_ownership
  owner                                               = each.value.owner
  policy                                              = each.value.policy
  putin_khuylo                                        = each.value.putin_khuylo
  region                                              = each.value.region
  replication_configuration                           = each.value.replication_configuration
  request_payer                                       = each.value.request_payer
  restrict_public_buckets                             = each.value.restrict_public_buckets
  server_side_encryption_configuration                = each.value.server_side_encryption_configuration
  skip_destroy_public_access_block                    = each.value.skip_destroy_public_access_block
  transition_default_minimum_object_size              = each.value.transition_default_minimum_object_size
  type                                                = each.value.type
  versioning                                          = each.value.versioning
  website                                             = each.value.website
}
