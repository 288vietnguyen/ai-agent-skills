#!/usr/bin/env python3
"""
Fetch Terraform coding standards (.md files) from an AWS S3 bucket.
The prefix and file list are configured via environment variables.

Environment variables:
    AWS_REGION              - AWS region for S3 (default: ap-southeast-1)
    AWS_ACCESS_KEY_ID       - AWS access key (or use IAM role)
    AWS_SECRET_ACCESS_KEY   - AWS secret key (or use IAM role)
    STANDARDS_PREFIX        - S3 key prefix (default: standards/)
    STANDARDS_FILES         - Comma-separated list of .md files to download
                              (e.g., structure.md,requirements.md,best_practices.md)

Usage:
    export STANDARDS_PREFIX="standards/"
    export STANDARDS_FILES="structure.md,requirements.md,best_practices.md"

    python3 fetch_standards.py --bucket my-standards-bucket --output-dir ./standards

Exit codes:
    0 - Standards fetched successfully
    1 - Failed to fetch standards
"""

import argparse
import json
import os
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def fetch_standards(bucket: str, prefix: str, files: list[str], output_dir: str, region: str) -> bool:
    """Download standard .md files from S3 to the output directory."""
    try:
        s3 = boto3.client("s3", region_name=region)
    except NoCredentialsError:
        print("ERROR: AWS credentials not configured. Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or use an IAM role.", file=sys.stderr)
        return False

    os.makedirs(output_dir, exist_ok=True)

    # Normalize prefix to end with /
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    downloaded = []
    missing = []

    for filename in files:
        s3_key = f"{prefix}{filename}"
        local_path = os.path.join(output_dir, filename)

        try:
            print(f"  Downloading s3://{bucket}/{s3_key} ...")
            s3.download_file(bucket, s3_key, local_path)
            downloaded.append({"file": filename, "s3_key": s3_key, "local_path": os.path.abspath(local_path)})
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404" or error_code == "NoSuchKey":
                print(f"  WARNING: {s3_key} not found in bucket.", file=sys.stderr)
                missing.append(filename)
            else:
                print(f"ERROR: Failed to download {s3_key}: {e}", file=sys.stderr)
                return False

    if missing:
        print(f"\nERROR: Missing standards files: {', '.join(missing)}", file=sys.stderr)
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Fetch Terraform standards from S3")
    parser.add_argument("--bucket", required=True, help="S3 bucket name containing standards")
    parser.add_argument("--output-dir", required=True, help="Local directory to download standards to")
    parser.add_argument("--prefix", default=None, help="S3 key prefix (overrides STANDARDS_PREFIX env var)")
    parser.add_argument("--files", nargs="+", default=None, help="List of .md files (overrides STANDARDS_FILES env var)")
    parser.add_argument("--region", default=None, help="AWS region (overrides AWS_REGION env var)")
    args = parser.parse_args()

    region = args.region or os.environ.get("AWS_REGION", "ap-southeast-1")
    prefix = args.prefix or os.environ.get("STANDARDS_PREFIX", "standards/")

    # Resolve file list: CLI arg > env var
    if args.files:
        files = args.files
    else:
        files_env = os.environ.get("STANDARDS_FILES", "")
        if not files_env:
            print("ERROR: No files specified. Set STANDARDS_FILES env var or use --files argument.", file=sys.stderr)
            sys.exit(1)
        files = [f.strip() for f in files_env.split(",") if f.strip()]

    if not files:
        print("ERROR: File list is empty.", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching {len(files)} standards file(s) from s3://{args.bucket}/{prefix} ...")
    print(f"  Files: {', '.join(files)}")

    if not fetch_standards(args.bucket, prefix, files, args.output_dir, region):
        sys.exit(1)

    # Output summary
    result = {
        "bucket": args.bucket,
        "prefix": prefix,
        "output_dir": os.path.abspath(args.output_dir),
        "files": files,
    }
    print(f"\n{json.dumps(result, indent=2)}")
    print("\nSUCCESS: Standards fetched.")


if __name__ == "__main__":
    main()
