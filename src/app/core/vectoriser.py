import json
from typing import Any

from core.config import get_config
from services.llm_service import get_azure_openai_client, get_boto_client


class TextVectoriser:
    def __init__(self, chunk_size: int = 300, overlap: int = 100):
        self.config = get_config()
        self.chunk_size = chunk_size
        self.overlap = overlap
        if self.config.hyperscaler == "AZURE":
            self.openai_client = get_azure_openai_client()
        elif self.config.hyperscaler == "AWS":
            self.bedrock_client = get_boto_client()

    def create_chunks(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        chunks = []
        text = text.strip()

        if len(text) <= self.chunk_size:
            return [text]

        start = 0
        while start < len(text):
            end = start + self.chunk_size

            # If this is not the last chunk, try to break at word boundary
            if end < len(text):
                # Find the last space within the chunk to avoid breaking words
                last_space = text.rfind(" ", start, end)
                line_break = text.rfind("\n", start, end)
                if max(last_space, line_break) > start:
                    end = max(last_space, line_break)

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position considering overlap
            start = end

            # Ensure the next chunk starts at a word boundary
            while start < len(text) and text[start].isspace():
                start += 1  # Skip whitespace to start at the next word

        return chunks

    def get_embedding(self, text: str) -> list[float]:
        """Get embedding for a single text using Amazon Titan."""
        try:
            if self.config.hyperscaler == "AWS":
                body = json.dumps(
                    {
                        "inputText": text,
                        "dimensions": 1024,  # Titan v2 supports up to 1024 dimensions
                        "normalize": True,
                    }
                )
                response = self.bedrock_client.invoke_model(modelId=self.config.aws.embedding_model_id, body=body, contentType="application/json")

                response_body = json.loads(response["body"].read())
                return response_body["embedding"]

            elif self.config.hyperscaler == "AZURE":
                response = self.openai_client.embeddings.create(
                    input=text,
                    model=self.config.azure.text_embedding_deployment,
                    dimensions=1024,
                )
                return response.data[0].embedding

        except Exception as e:
            print(f"Error getting embedding: {e}")
            raise

    def vectorise_text(self, text: str) -> list[dict[str, Any]]:
        """
        Vectorise text by chunking and creating embeddings.

        Args:
            text: The text content to vectorise
            source_file: The source filename
            file_date: The file date (optional)

        Returns:
            List of dictionaries containing chunk text, vector, and metadata
        """
        chunks = self.create_chunks(text)
        vectorised_chunks = []

        for i, chunk in enumerate(chunks):
            try:
                embedding = self.get_embedding(chunk)

                vectorised_chunk = {
                    "chunk_text": chunk,
                    "embedding": embedding,
                    "metadata": {
                        "chunk_index": i,
                        "chunk_size": len(chunk),
                        "total_chunks": len(chunks),
                    },
                }
                vectorised_chunks.append(vectorised_chunk)

                # Clear embedding data to free memory
                del embedding

            except Exception as e:
                print(f"Error vectorizing chunk {i}: {e}")
                continue

        # Explicitly clear chunks list to free memory
        del chunks

        return vectorised_chunks
