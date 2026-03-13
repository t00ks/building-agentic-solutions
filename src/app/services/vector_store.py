import os
import re
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np
import psycopg
from sklearn.cluster import AgglomerativeClustering

from core.config import get_config
from core.logging_config import get_logger
from core.vectoriser import TextVectoriser

TABLE_NAME = os.getenv("VECTOR_TABLE", "document_vectors")
VECTOR_DIM = 1024


def simple_sentence_tokenize(text):
    """Simple fallback sentence tokenizer that splits on common sentence terminators."""
    # Split on period, question mark, or exclamation mark followed by space or newline
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


class VectorStore(ABC):
    """
    Vector Store class to handle vector operations in a PostgreSQL database.

    This class encapsulates the logic for connecting to the database and performing vector operations.
    """  # noqa: E501

    def __init__(self):
        """
        Initialize the Vector Store with a connection to the PostgreSQL database.
        """
        self.config = get_config()
        conn_info = self.config.database.postgres_uri
        if not conn_info:
            raise ValueError("POSTGRES_URI environment variable not set")

        self.conn = psycopg.connect(conn_info)

        self.vectoriser = TextVectoriser()
        self.use_nltk = self._try_load_nltk()

        self.logger = get_logger(__name__)

    @property
    @abstractmethod
    def table_name(self):
        pass

    def _try_load_nltk(self):
        """
        Try to load NLTK resources and return True if successful, False otherwise.
        Uses the default NLTK data path and downloads 'punkt' if missing.
        """
        try:
            # Disable SSL verification before importing NLTK (for macOS SSL issues)
            import ssl

            ssl._create_default_https_context = ssl._create_unverified_context

            import nltk

            # Download 'punkt' to the default location if not present
            try:
                nltk.data.find("tokenizers/punkt")
            except LookupError:
                nltk.download("punkt", quiet=True)

            # Test if it works
            test = nltk.sent_tokenize("This is a test. This is another test.")
            if len(test) == 2:
                self.nltk = nltk
                return True

        except Exception as e:
            self.logger.error(f"NLTK setup failed: {e}")
            traceback.print_exc()
            self.logger.warning("Will use fallback tokenization method")

        return False

    def _extract_topics_semantic(self, query: str) -> list[str]:
        """
        Extract topics from a query using semantic understanding via embeddings.
        """
        # Always include the original query
        topics = [query]

        # Split into sentences using appropriate tokenizer
        if self.use_nltk:
            sentences = self.nltk.sent_tokenize(query)
        else:
            # Use fallback tokenizer if NLTK is unavailable
            sentences = simple_sentence_tokenize(query)

        # Split further into text units (spans) that might represent distinct topics
        text_units = []
        for sentence in sentences:
            # If sentence is short, keep it whole
            if len(sentence.split()) < 10:
                text_units.append(sentence)
            else:
                # For longer sentences, try to break down further
                # Split on common conjunctions and punctuation that often separate topics
                potential_splits = re.split(r"\band\b|\bor\b|\bas well as\b|;|,", sentence)
                for split in potential_splits:
                    clean_split = split.strip()
                    if (
                        clean_split and len(clean_split.split()) >= 3
                    ):  # Only keep meaningful phrases
                        text_units.append(clean_split)

        # If we don't have enough units to cluster, return early
        if len(text_units) <= 1:
            return topics

        # Get embeddings for each text unit
        embeddings = [self.vectoriser.get_embedding(unit) for unit in text_units]

        # Convert to numpy array for clustering
        embeddings_array = np.array(embeddings)

        # Determine number of clusters (topics)
        # Calculate a reasonable number based on the query complexity
        max_clusters = min(len(text_units), max(2, len(text_units) // 2))

        # Cluster the text unit embeddings
        clustering = AgglomerativeClustering(
            n_clusters=max_clusters, metric="euclidean", linkage="ward"
        ).fit(embeddings_array)

        # Group text units by cluster
        clusters = {}
        for i, cluster_id in enumerate(clustering.labels_):
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(text_units[i])

        # Create a topic from each cluster by joining its text units
        for _, cluster_units in clusters.items():
            topic = " ".join(cluster_units)
            if topic not in topics:  # Avoid duplicates
                topics.append(topic)

        return topics

    def _generate_query_variations(self, query: str) -> list[str]:
        """
        Generate variations of the query to improve retrieval.
        Works for any topic, not just specific domains.
        """
        variations = []

        # Extract important words - focus on nouns, verbs, and adjectives
        # Simple regex-based approach
        words = re.findall(r"\b[A-Za-z]{4,}\b", query)

        # If it's a question, create a version without question words
        if "?" in query:
            # Remove common question words
            question_reduced = re.sub(
                r"\b(what|how|where|when|which|who|why|can|should|is|are|do|does)\b",
                "",
                query,
                flags=re.IGNORECASE,
            )
            question_reduced = re.sub(r"\s+", " ", question_reduced).strip()
            if (
                question_reduced
                and question_reduced not in variations
                and question_reduced != query
            ):
                variations.append(question_reduced)

        # Create keyword-based query
        if len(words) >= 2:
            # Focus on most important words (longer words tend to carry more meaning)
            important_words = sorted(words, key=len, reverse=True)[:5]
            keyword_query = " ".join(important_words)
            if keyword_query not in variations and keyword_query != query:
                variations.append(keyword_query)

        # Handle "advantages and disadvantages" type queries
        if any(
            term in query.lower()
            for term in ["advantage", "disadvantage", "benefit", "drawback", "pros", "cons"]
        ):
            # Get the subject by removing these comparison terms
            subject = re.sub(
                r"\b(advantages?|disadvantages?|benefits?|drawbacks?|pros|cons|of|and)\b",
                "",
                query,
                flags=re.IGNORECASE,
            )
            subject = re.sub(r"\s+", " ", subject).strip()

            if len(subject) >= 4:
                comparison_variations = [
                    f"{subject} benefits",
                    f"{subject} drawbacks",
                    f"{subject} comparison",
                ]
                variations.extend(comparison_variations)

        # For queries asking about steps, processes or methods
        if any(
            term in query.lower() for term in ["how to", "steps", "process", "method", "procedure"]
        ):
            subject = re.sub(
                r"\b(how|to|steps|process|method|procedure|for|of)\b",
                "",
                query,
                flags=re.IGNORECASE,
            )
            subject = re.sub(r"\s+", " ", subject).strip()

            if len(subject) >= 4:
                how_to_variations = [
                    f"{subject} steps",
                    f"{subject} guide",
                    f"{subject} instructions",
                ]
                variations.extend(how_to_variations)

        # Simplify the query by removing common filler words
        simplified = re.sub(
            r"\b(the|a|an|in|on|for|to|with|by|at|from|of)\b", "", query, flags=re.IGNORECASE
        )
        simplified = re.sub(r"\s+", " ", simplified).strip()
        if simplified and simplified not in variations and simplified != query:
            variations.append(simplified)

        # Return unique variations
        return list(set(variations))

    @abstractmethod
    def _retrieve_for_single_query(self, query: str, top_k: int = 10) -> list[tuple]:
        """
        Retrieve relevant context chunks for a single query topic.
        """
        raise NotImplementedError("Subclasses must implement _retrieve_for_single_query method.")

    @abstractmethod
    def _get_result_embeddings(self, results: list[tuple]) -> list[list[float]]:
        """
        Get embeddings for the result texts.
        """
        raise NotImplementedError("Subclasses must implement _get_result_embeddings method.")

    def _sort_results_by_relevance(self, query: str, results: list[tuple]) -> list[tuple]:
        """
        Sort results by their relevance to the original query.
        """
        if len(results) <= 1:
            return results

        try:
            # Get embeddings
            query_embedding = self.vectoriser.get_embedding(query)
            result_embeddings = self._get_result_embeddings(results)

            # Calculate cosine similarities
            similarities = []
            for embedding in result_embeddings:
                dot_product = np.dot(query_embedding, embedding)
                norm_product = np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
                similarity = dot_product / norm_product if norm_product != 0 else 0
                similarities.append(similarity)

            # Sort results by similarity (highest first)
            sorted_indices = np.argsort(similarities)[::-1]
            sorted_results = [results[i] for i in sorted_indices]

            return sorted_results

        except Exception as e:
            self.logger.error(f"Error during result sorting: {e}")
            # Return original results if sorting fails
            return results

    @abstractmethod
    def _format_result(self, result: tuple) -> str:
        """
        Format a single result tuple into a string for output.
        """
        pass

    def retrieve_context(
        self,
        query: str,
        search_variations: bool,
        sort_by_relevance: bool = False,
        top_k: int = 10,
        min_results: int = 5,
        context_sort: Callable[[list[tuple]], list[tuple]] | None = None,
    ) -> list[str]:
        """
        Retrieve relevant context chunks for a given query from a pgvector table.

        This implementation improves recall by:

        1. Extracting multiple topics from the query semantically
        2. Generating query variations to improve coverage
        3. Retrieving context for each topic and variation separately
        4. Combining the results with deduplication
        5. Sorting by relevance to the original query
        6. Applying an optional custom sorting function based on the current page context
        """
        # Extract topics from the query using semantic understanding
        base_topics = self._extract_topics_semantic(query)

        if search_variations:
            # Generate query variations for better coverage
            variations = self._generate_query_variations(query)

        # Calculate how many results to retrieve per topic
        # Ensure base topics get more results
        base_per_topic_k = max(min_results, top_k // max(1, len(base_topics)))
        variation_per_topic_k = max(2, min_results // 2)  # Fewer results for variations

        # Track unique results to avoid duplicates
        seen_chunks = set()
        results = []

        # First retrieve for base topics with higher allocation
        for topic in base_topics:
            topic_results = self._retrieve_for_single_query(topic, base_per_topic_k)

            for row in topic_results:
                chunk_id = row[0]
                if chunk_id not in seen_chunks:
                    seen_chunks.add(chunk_id)
                    results.append(row)

        if search_variations:
            # Then retrieve for variations with lower allocation
            for variation in variations:
                # Skip if we already have enough results
                if len(results) >= top_k * 2:  # Get more than we need for sorting
                    break

                var_results = self._retrieve_for_single_query(variation, variation_per_topic_k)

                for row in var_results:
                    chunk_id = row[0]
                    if chunk_id not in seen_chunks:
                        seen_chunks.add(chunk_id)
                        results.append(row)

        # Sort results by relevance to the original query
        sorted_results = self._sort_results_by_relevance(query, results) if sort_by_relevance else results

        if context_sort:
            try:
                sorted_results = context_sort(sorted_results)
            except Exception as e:
                self.logger.error(f"Error during custom context sorting: {e}")

        # Format and return the top results
        formatted_results = [self._format_result(row) for row in sorted_results[:top_k]]
        return formatted_results


class KnowledgeStore(VectorStore):
    """
    Mortgage Knowledge Store class to handle mortgage-related vector operations.
    """

    def __init__(self):
        super().__init__()

    @property
    def table_name(self):
        return self.config.database.document_table

    def _get_result_embeddings(self, results: list[tuple]) -> list[list[float]]:
        """
        Get embeddings for the result texts.
        """
        return [self.vectoriser.get_embedding(text) for _, text in results]

    def _retrieve_for_single_query(self, query: str, top_k: int = 10) -> list[tuple]:
        """
        Retrieve relevant context chunks for a single query topic.
        """
        query_embedding = self.vectoriser.get_embedding(query)

        with self.conn.cursor() as cursor:
            from psycopg.sql import SQL, Identifier, Placeholder

            sql_query = SQL("""
                SELECT chunk_index, chunk_text
                FROM {}
                ORDER BY vector <=> {}::vector
                LIMIT {};
                """).format(Identifier(self.table_name), Placeholder(), Placeholder())

            cursor.execute(sql_query, (query_embedding, top_k))
            results = cursor.fetchall()
            self.conn.commit()

        return results

    def _format_result(self, result: tuple) -> str:
        """
        Format a single result tuple into a string for output.
        """
        return f"[Source: {result[0]}] {result[1]}"