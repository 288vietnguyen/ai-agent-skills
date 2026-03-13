output "s3_bucket_arn" {
  description = "The ARN of the bucket. Will be of format arn:aws:s3:::bucketname."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_arn if module.s3-label[k].enabled }
}

output "aws_s3_bucket_versioning_status" {
  description = "The versioning status of the bucket. Will be 'Enabled', 'Suspended', or 'Disabled'."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].aws_s3_bucket_versioning_status if module.s3-label[k].enabled }
}

output "s3_bucket_bucket_domain_name" {
  description = "The bucket domain name. Will be of format bucketname.s3.amazonaws.com."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_bucket_domain_name if module.s3-label[k].enabled }
}

output "s3_bucket_bucket_regional_domain_name" {
  description = "The bucket region-specific domain name."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_bucket_regional_domain_name if module.s3-label[k].enabled }
}

output "s3_bucket_hosted_zone_id" {
  description = "The Route 53 Hosted Zone ID for this bucket's region."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_hosted_zone_id if module.s3-label[k].enabled }
}

output "s3_bucket_id" {
  description = "The name of the bucket."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_id if module.s3-label[k].enabled }
}

output "s3_bucket_lifecycle_configuration_rules" {
  description = "The lifecycle rules of the bucket, if the bucket is configured with lifecycle rules. If not, this will be an empty string."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_lifecycle_configuration_rules if module.s3-label[k].enabled }
}

output "s3_bucket_policy" {
  description = "The policy of the bucket, if the bucket is configured with a policy. If not, this will be an empty string."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_policy if module.s3-label[k].enabled }
}

output "s3_bucket_region" {
  description = "The AWS region this bucket resides in."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_region if module.s3-label[k].enabled }
}

output "s3_bucket_tags" {
  description = "Tags of the bucket."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_tags if module.s3-label[k].enabled }
}

output "s3_bucket_website_domain" {
  description = "The domain of the website endpoint, if the bucket is configured with a website. If not, this will be an empty string. This is used to create Route 53 alias records."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_website_domain if module.s3-label[k].enabled }
}

output "s3_bucket_website_endpoint" {
  description = "The website endpoint, if the bucket is configured with a website. If not, this will be an empty string."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_bucket_website_endpoint if module.s3-label[k].enabled }
}

output "s3_directory_bucket_arn" {
  description = "ARN of the directory bucket."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_directory_bucket_arn if module.s3-label[k].enabled }
}

output "s3_directory_bucket_name" {
  description = "Name of the directory bucket."
  value = { for k, v in var.s3_buckets : k => module.s3-bucket[k].s3_directory_bucket_name if module.s3-label[k].enabled }
}