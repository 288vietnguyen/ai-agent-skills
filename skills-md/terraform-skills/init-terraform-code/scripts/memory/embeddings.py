#!/usr/bin/env python3
"""Bedrock Cohere Embed V4 wrapper for generating embeddings."""

import json
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

EMBEDDING_MODEL = "cohere.embed-v4:0"


class BedrockEmbeddings:
    """Generate text embeddings using Amazon Bedrock Cohere Embed V4."""

    def __init__(self, region: str):
        self.model_id = EMBEDDING_MODEL
        self.dimensions = None
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
            A list of floats representing the embedding vector.
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
            vector = result["embeddings"]["float"][0]

            # Set dimensions on first call
            if self.dimensions is None:
                global EMBEDDING_DIMENSIONS
                self.dimensions = len(vector)
                EMBEDDING_DIMENSIONS = self.dimensions
                print(f"  Embedding model {self.model_id}: {self.dimensions} dimensions")

            return vector

        except ClientError as e:
            print(f"ERROR: Bedrock embedding failed: {e}", file=sys.stderr)
            raise
