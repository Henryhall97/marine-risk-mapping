"""Upload raw data files to S3.

Walks through data/raw/ and uploads all files to S3,
mirroring the local folder structure. Skips files that
already exist in S3.
"""

import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

S3_BUCKET = "marine-risk-mapping-hh"  # change to your preferred bucket name
S3_PREFIX = "raw/"
LOCAL_DATA_DIR = Path("data/raw")
AWS_REGION = "eu-west-2"  # change to your preferred region
EXCLUDE_DIRS = {"occurrence"}  # folders to skip (unfiltered data)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def ensure_bucket_exists(client, bucket: str, region: str) -> None:
    """Create the S3 bucket if it doesn't already exist.

    Args:
        client: boto3 S3 client.
        bucket: Name of the S3 bucket.
        region: AWS region for the bucket.
    """
    try:
        client.head_bucket(Bucket=bucket)
        logger.info("Bucket %s already exists", bucket)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            logger.info("Creating bucket %s in %s", bucket, region)
            if region == "us-east-1":
                client.create_bucket(Bucket=bucket)
            else:
                client.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
            logger.info("Bucket %s created", bucket)
        else:
            raise


def file_exists_in_s3(client, bucket: str, key: str) -> bool:
    """Check whether a file already exists in S3.

    Args:
        client: boto3 S3 client.
        bucket: Name of the S3 bucket.
        key: S3 object key (the "path" in the bucket).

    Returns:
        True if the object exists, False otherwise.
    """
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def upload_raw_data() -> None:
    """Upload all raw data files to S3."""
    client = boto3.client("s3", region_name=AWS_REGION)

    # Step 1: Ensure bucket exists
    ensure_bucket_exists(client, S3_BUCKET, AWS_REGION)

    # Step 2: Find all files in data/raw/ (excluding certain directories)
    files = [
        f
        for f in LOCAL_DATA_DIR.rglob("*")
        if f.is_file()
        and f.name != ".gitkeep"
        and not any(
            part in EXCLUDE_DIRS for part in f.relative_to(LOCAL_DATA_DIR).parts
        )
    ]
    logger.info("Found %d files to upload", len(files))

    uploaded = 0
    skipped = 0
    failed = 0

    for i, file_path in enumerate(files, start=1):
        # Build the S3 key from the local path
        relative_path = file_path.relative_to(LOCAL_DATA_DIR)
        s3_key = S3_PREFIX + str(relative_path)

        # Skip if already uploaded
        if file_exists_in_s3(client, S3_BUCKET, s3_key):
            logger.info("(%d/%d) Skipping %s — already exists", i, len(files), s3_key)
            skipped += 1
            continue

        # Upload
        try:
            size_mb = file_path.stat().st_size / 1e6
            logger.info(
                "(%d/%d) Uploading %s (%.1f MB)", i, len(files), s3_key, size_mb
            )
            client.upload_file(str(file_path), S3_BUCKET, s3_key)
            uploaded += 1
        except ClientError as e:
            logger.error("Failed to upload %s: %s", s3_key, e)
            failed += 1

    logger.info(
        "Upload complete: %d uploaded, %d skipped, %d failed",
        uploaded,
        skipped,
        failed,
    )


if __name__ == "__main__":
    upload_raw_data()
