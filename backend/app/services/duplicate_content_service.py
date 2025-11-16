import difflib
from typing import List, Dict, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from bs4 import BeautifulSoup
import re

class DuplicateContentService:
    
    @staticmethod
    def extract_text(html: str) -> str:
        """Extrae texto limpio del HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return re.sub(r'\s+', ' ', text)
    
    @staticmethod
    def similarity_ratio(text1: str, text2: str) -> float:
        """Calcula similitud usando difflib (0-1)"""
        return difflib.SequenceMatcher(None, text1, text2).ratio()
    
    @staticmethod
    def tfidf_similarity(texts: List[str]) -> np.ndarray:
        """Calcula matriz de similitud TF-IDF"""
        if len(texts) < 2:
            return np.array([[1.0]])
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        tfidf_matrix = vectorizer.fit_transform(texts)
        return cosine_similarity(tfidf_matrix)
    
    @staticmethod
    def find_duplicates(pages: List[Dict], threshold: float = 0.85) -> List[Dict]:
        """Encuentra contenido duplicado entre páginas"""
        if len(pages) < 2:
            return []
        
        texts = [DuplicateContentService.extract_text(p.get('html', '')) for p in pages]
        urls = [p.get('url', '') for p in pages]
        
        similarity_matrix = DuplicateContentService.tfidf_similarity(texts)
        
        duplicates = []
        for i in range(len(pages)):
            for j in range(i + 1, len(pages)):
                similarity = similarity_matrix[i][j]
                if similarity >= threshold:
                    duplicates.append({
                        'url1': urls[i],
                        'url2': urls[j],
                        'similarity': float(similarity),
                        'type': 'internal'
                    })
        
        return duplicates
    
    @staticmethod
    def compare_external(internal_text: str, external_texts: List[Tuple[str, str]], threshold: float = 0.75) -> List[Dict]:
        """Compara contenido interno con externo"""
        results = []
        for url, text in external_texts:
            similarity = DuplicateContentService.similarity_ratio(internal_text, text)
            if similarity >= threshold:
                results.append({
                    'external_url': url,
                    'similarity': similarity,
                    'type': 'external'
                })
        return results
