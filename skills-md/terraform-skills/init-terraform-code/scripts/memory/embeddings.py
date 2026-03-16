#!/usr/bin/env python3
"""Bedrock Cohere Embed V4 wrapper for generating embeddings."""

import json
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

DEFAULT_EMBEDDING_MODEL = "cohere.embed-v4:0"
EMBEDDING_DIMENSIONS = 1024


class BedrockEmbeddings:
    """Generate text embeddings using Amazon Bedrock Cohere Embed V4."""

    def __init__(self, region: str, model_id: str = DEFAULT_EMBEDDING_MODEL):
        self.model_id = model_id
        self.dimensions = EMBEDDING_DIMENSIONS
        try:
            self.client = boto3.client("bedrock-runtime", region_name=region)
        except NoCredentialsError:
            print("ERROR: AWS credentials not configured for Bedrock embeddings.", file=sys.stderr)
            raise

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a vector.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector (1024 dimensions).
        """
        body = json.dumps({
            "texts": [text],
            "input_type": "search_document",
            "embedding_types": ["float"],
        })

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            result = json.loads(response["body"].read())
            return result["embeddings"]["float"][0]

        except ClientError as e:
            print(f"ERROR: Bedrock embedding failed: {e}", file=sys.stderr)
            raise
