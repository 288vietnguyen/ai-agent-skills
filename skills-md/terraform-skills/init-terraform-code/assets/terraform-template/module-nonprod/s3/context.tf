module "this" {
  source = "cloudposse/label/null"      # Change the source depend on the Organization Policy

  version = "0.25.0"                    # Change module's Version depend on the Organization Policy

  enabled = var.enabled
  context = var.context
  tags    = var.context.tags
}

variable "context" {
  type = any

  default = {
    enabled             = true
    namespace           = null
    tenant              = null
    environment         = null
    stage               = null
    name                = null
    delimiter           = null
    attributes          = []
    tags                = {}
    additional_tag_map  = {}
    regex_replace_chars = null
    labe_order          = []
    id_length_limit     = null
    label_key_case      = null
    label_value_case    = null
    descriptor_formats  = {}

    labels_as_tags      = ["unset"]
  }

  description = <<-EOT
  Terraform module designed to generate consistent label names and tags for resources. 
  Use terraform-terraform-label to implement a strict naming convention.
  A label follows the following convention: {namespace}-{stage}-{name}-{attributes}. The delimiter (e.g. -) is interchangeable.
  EOT

  validation {
    condition = lookup(var.context, "label_key_case", null) == null ? true : contains(["lower", "title", "upper"], var.context["label_key_case"])
    error_message = "Allowed values: `lower`, `title`, `upper`."
  }

  validation {
    condition = lookup(var.context, "label_value_case", null) == null ? true : contains(["lower", "title", "upper", "none"], var.context["label_value_case"])
    error_message = "Allowed values: `lower`, `title`, `upper`, `none`."
  }

}

variable "enabled" {
  type        = bool
  default     = null
  description = "Set to false to prevent the module from creating any resources"
}

variable "attributes" {
  type        = list(string)
  default     = []
  description = "Additional attributes (e.g. `1`)"
}