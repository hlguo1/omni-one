terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
  # Remote state is REQUIRED for anything beyond a demo — see README.md.
  # backend "s3" {
  #   bucket         = "omni-one-tfstate-CHANGE_ME"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "omni-one-tfstate-locks"
  # }
}
