"""
Duplicate Content Detection Service
Detects duplicate content within site and against competitors.
Uses TF-IDF when sklearn is available, falls back to difflib otherwise.
"""
import difflib
import re
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

# Make sklearn optional - not critical for core functionality
try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    np = None


class DuplicateContentService:
    """Service for detecting duplicate content across pages."""

    @staticmethod
    def extract_text(html: str) -> str:
        """Extrae texto limpio del HTML"""
        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def similarity_ratio(text1: str, text2: str) -> float:
        """Calcula similitud usando difflib (0-1)"""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    @staticmethod
    def tfidf_similarity(texts: List[str]) -> List[List[float]]:
        """
        Calcula matriz de similitud.
        Uses TF-IDF if sklearn available, otherwise uses difflib.
        """
        if len(texts) < 2:
            return [[1.0]]

        if SKLEARN_AVAILABLE:
            # Use sklearn TF-IDF for better accuracy
            vectorizer = TfidfVectorizer(stop_words="english", max_features=1000)
            tfidf_matrix = vectorizer.fit_transform(texts)
            return cosine_similarity(tfidf_matrix).tolist()
        else:
            # Fallback to difflib-based similarity matrix
            n = len(texts)
            similarity_matrix = [[0.0] * n for _ in range(n)]

            for i in range(n):
                for j in range(n):
                    if i == j:
                        similarity_matrix[i][j] = 1.0
                    elif j > i:
                        sim = difflib.SequenceMatcher(None, texts[i], texts[j]).ratio()
                        similarity_matrix[i][j] = sim
                        similarity_matrix[j][i] = sim

            return similarity_matrix

    @staticmethod
    def find_duplicates(pages: List[Dict], threshold: float = 0.85) -> List[Dict]:
        """
        Encuentra contenido duplicado entre páginas.
        Useful for SEO - Google penalizes duplicate content.
        """
        if len(pages) < 2:
            return []

        texts = [DuplicateContentService.extract_text(p.get("html", "")) for p in pages]
        urls = [p.get("url", "") for p in pages]

        similarity_matrix = DuplicateContentService.tfidf_similarity(texts)

        duplicates = []
        for i in range(len(pages)):
            for j in range(i + 1, len(pages)):
                similarity = similarity_matrix[i][j]
                if similarity >= threshold:
                    duplicates.append(
                        {
                            "url1": urls[i],
                            "url2": urls[j],
                            "similarity": float(similarity),
                            "type": "internal",
                            "recommendation": "Consolidar contenido o usar canonical tags",
                        }
                    )

        return duplicates

    @staticmethod
    def compare_external(
        internal_text: str,
        external_texts: List[Tuple[str, str]],
        threshold: float = 0.75,
    ) -> List[Dict]:
        """
        Compara contenido interno con externo.
        Detects if competitors have copied your content or vice versa.
        """
        results = []
        for url, text in external_texts:
            similarity = DuplicateContentService.similarity_ratio(internal_text, text)
            if similarity >= threshold:
                results.append(
                    {
                        "external_url": url,
                        "similarity": similarity,
                        "type": "external",
                        "recommendation": "Verificar originalidad y fechas de publicación",
                    }
                )
        return results

    @staticmethod
    def get_similarity_method() -> str:
        """Returns which similarity method is being used."""
        return "TF-IDF (sklearn)" if SKLEARN_AVAILABLE else "difflib (fallback)"
