#!/usr/bin/env python3
"""
ILMA Indonesian NLP Engine v1.0
Native Bahasa Indonesia processing - stemming, normalization, keyword extraction
"""
import re
import json
import math
from typing import List, Dict, Set, Tuple, Optional
from collections import Counter

# Indonesian stopwords
STOPWORDS = {
    'yang', 'dan', 'di', 'dari', 'dengan', 'untuk', 'pada', 'adalah', 'ini', 'itu',
    'tersebut', 'tidak', 'akan', 'juga', 'ada', 'atau', 'oleh', 'sudah', 'lebih',
    'sebagai', 'dapat', 'telah', 'ke', 'dalam', 'na', 'ya', 'nya', 'pun', 'lah',
    'yg', 'jg', 'utk', 'dr', 'pd', 'sm', 'tp', 'kalo', 'kl', 'sdh', 'blm', 'bs',
    'bgt', 'jg', 'spt', 'krn', 'karna', 'karena', 'maka', 'jika', 'kalau', 'bila',
    'bahwa', 'jadi', 'mau', 'perlu', 'harus', 'bisa', 'hanya', 'begitu', 'tetapi',
    'namun', 'walau', 'meski', 'meskipun', 'agar', 'supaya', 'hingga', 'sampai',
    'padahal', 'sedang', 'sambil', 'serta', 'ataupun', 'maupun', 'lagi', 'lg',
    'btw', 'ntar', 'nih', 'dong', 'deh', 'sih', 'tuh', 'kan', 'kok', 'emang',
    'memang', 'dong', 'ajah', 'aja', 'banget', 'bgt', 'gitu', 'gt', 'kek',
    'gimana', 'gmana', 'dapet', 'dpt', 'trus', 'terus', 'kalo', 'kalau'
}

# Indonesian morphological rules for stemming
PREFIXES = [
    'me', 'mem', 'men', 'meng', 'meny', 'pe', 'pem', 'pen', 'peng', 'peny',
    'ber', 'be', 'ter', 'ke', 'pe', 'per', 'pel', 'se', 'ter', 'di', 'ter'
]

SUFFIXES = ['kan', 'an', 'i', 'kan', 'nya', 'pun', 'lah', 'kah', 'tah']

def normalize_text(text: str) -> str:
    """Normalize Indonesian text - lowercase, remove special chars."""
    text = text.lower()
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove mentions and hashtags
    text = re.sub(r'[@#]\S+', '', text)
    # Normalize repeated chars
    text = re.sub(r'(.)\1{2,}', r'\1\1', text)
    # Keep only letters, numbers, spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text

def indonesian_stem(word: str) -> str:
    """
    Simple Indonesian stemming using prefix/suffix stripping.
    Not perfect but good enough for keyword extraction.
    """
    word = word.lower().strip()
    if len(word) <= 3:
        return word
    
    # Handle common prefix patterns
    if word.startswith('meng'):
        word = 'k' + word[4:] if word[4:] else word
    elif word.startswith('meny'):
        word = 's' + word[4:] if word[4:] else word
    elif word.startswith('men'):
        word = 't' + word[3:] if word[3:] else word
    elif word.startswith('mem'):
        word = 'p' + word[3:] if word[3:] else word
    elif word.startswith('me'):
        word = word[2:] if word[2:] else word
    elif word.startswith('ber'):
        word = word[3:] if word[3:] else word
    elif word.startswith('ter'):
        word = word[3:] if word[3:] else word
    elif word.startswith('ke'):
        word = word[2:] if word[2:] else word
    elif word.startswith('per'):
        word = word[3:] if word[3:] else word
    elif word.startswith('pe'):
        word = word[2:] if word[2:] else word
    
    # Handle suffix patterns
    for suffix in ['kan', 'nya', 'pun', 'i', 'an']:
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            word = word[:-len(suffix)]
            break
    
    return word

def preprocess(text: str, remove_stopwords: bool = True) -> List[str]:
    """Tokenize and stem Indonesian text."""
    normalized = normalize_text(text)
    tokens = normalized.split()
    
    # Stem each token
    stemmed = [indonesian_stem(token) for token in tokens]
    
    # Remove stopwords if requested
    if remove_stopwords:
        stemmed = [t for t in stemmed if t not in STOPWORDS and len(t) > 2]
    
    return stemmed

def extract_keywords(text: str, top_n: int = 10) -> List[Tuple[str, float]]:
    """Extract keywords using TF-IDF-like scoring."""
    tokens = preprocess(text, remove_stopwords=True)
    
    if not tokens:
        return []
    
    # TF scoring
    tf = Counter(tokens)
    total = len(tokens)
    
    # IDF-like scoring (simplified - assumes all docs have same terms)
    # In real implementation, would use corpus statistics
    idf = {word: 1.0 for word in tf}
    
    # TF-IDF scores
    scores = {}
    for word, count in tf.items():
        tf_score = count / total
        idf_score = idf.get(word, 1.0)
        scores[word] = tf_score * idf_score
    
    # Sort by score
    sorted_words = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_words[:top_n]

def extract_keyphrases(text: str, top_n: int = 5) -> List[str]:
    """Extract 2-3 word phrases from text."""
    normalized = normalize_text(text)
    tokens = normalized.split()
    
    phrases = []
    for i in range(len(tokens) - 1):
        # Skip if either word is a stopword
        if tokens[i] in STOPWORDS or tokens[i+1] in STOPWORDS:
            continue
        phrase = f"{tokens[i]} {tokens[i+1]}"
        phrases.append(phrase)
    
    # Score by frequency
    phrase_counts = Counter(phrases)
    top_phrases = phrase_counts.most_common(top_n * 2)
    
    # Filter short phrases and return top_n
    result = [p[0] for p in top_phrases if len(p[0]) > 6][:top_n]
    return result

def boost_intent_signals(text: str, intents: List[str]) -> Dict[str, float]:
    """Boost intent detection signals based on Indonesian patterns."""
    normalized = normalize_text(text)
    tokens = set(preprocess(normalized, remove_stopwords=False))
    
    intent_keywords = {
        'greeting': ['halo', 'hai', 'helo', 'pagi', 'siang', 'sore', 'malam', 'selamat'],
        'build': ['bikin', 'buat', 'buat', 'bangun', 'create', 'develop', 'implement'],
        'fix': ['perbaiki', 'fix', 'bug', 'error', 'gagal', 'masalah', 'issue'],
        'search': ['cari', 'search', 'tolong', 'bantu', 'carikan'],
        'optimize': ['optim', 'perbaik', 'tingkat', 'cepat', 'lambat'],
        'research': ['riset', 'pelajar', 'cari', 'tahu', 'telusuri'],
        'delete': ['hapus', 'delete', 'buang', 'hilang'],
        'update': ['update', 'perbarui', 'ubah', 'ganti'],
        'deploy': ['deploy', 'terbit', 'rilis', 'launch'],
        'coding': ['kode', 'code', 'python', 'script', 'program'],
        'review': ['review', 'cek', 'tinjau', 'audit', 'periksa'],
        'debug': ['debug', 'trace', 'bug', 'error', 'masalah'],
        'test': ['test', 'uji', 'coba', 'tes'],
    }
    
    scores = {}
    for intent, keywords in intent_keywords.items():
        score = sum(1 for kw in keywords if kw in normalized) / len(keywords)
        if intent in intents:
            scores[intent] = score * 1.5  # Boost if already detected
        else:
            scores[intent] = score
    
    return scores

def analyze_sentiment(text: str) -> Dict[str, float]:
    """Simple sentiment analysis for Indonesian."""
    normalized = normalize_text(text)
    tokens = set(preprocess(normalized, remove_stopwords=False))
    
    positive = {
        'baik', 'bagus', 'senang', 'happy', 'cantik', 'keren', 'great', 'good',
        'mantap', 'top', 'keren', 'sukses', 'berhasil', 'lancar', 'easy', 'cepat'
    }
    negative = {
        'buruk', 'jelek', 'busuk', 'gagal', 'fail', 'error', 'bug', 'masalah',
        'sulit', 'salah', 'ralat', 'parah', 'lambat', 'bad', 'sick', 'dead'
    }
    urgent = {
        'urgent', 'segera', 'sekarang', 'asap', 'critical', 'mendesak', 'kritis'
    }
    
    pos_count = len(tokens & positive)
    neg_count = len(tokens & negative)
    urgent_count = len(tokens & urgent)
    
    total = max(len(tokens), 1)
    
    return {
        'positive': pos_count / total,
        'negative': neg_count / total,
        'urgent': urgent_count / total,
        'polarity': (pos_count - neg_count) / total,
        'overall': 'positive' if pos_count > neg_count else 'negative' if neg_count > pos_count else 'neutral'
    }

def get_text_summary(text: str, max_sentences: int = 3) -> str:
    """Extract most important sentences from text."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    if len(sentences) <= max_sentences:
        return '. '.join(sentences) + '.'
    
    # Score sentences by keyword density
    keywords = set(word for word, _ in extract_keywords(text, top_n=15))
    
    scored = []
    for sent in sentences:
        sent_tokens = set(preprocess(sent, remove_stopwords=True))
        density = len(sent_tokens & keywords) / max(len(sent_tokens), 1)
        scored.append((sent, density))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    top_sentences = [s[0] for s in scored[:max_sentences]]
    
    # Return in original order
    result = []
    for sent in sentences:
        if sent in top_sentences and len(result) < max_sentences:
            result.append(sent)
    
    return '. '.join(result) + '.'

def analyze_text(text: str) -> Dict:
    """Comprehensive Indonesian text analysis."""
    tokens = preprocess(text, remove_stopwords=True)
    keywords = extract_keywords(text, top_n=10)
    phrases = extract_keyphrases(text, top_n=5)
    sentiment = analyze_sentiment(text)
    
    return {
        'original_length': len(text),
        'token_count': len(tokens),
        'unique_tokens': len(set(tokens)),
        'keywords': [{'word': w, 'score': round(s, 4)} for w, s in keywords],
        'keyphrases': phrases,
        'sentiment': sentiment,
        'language_hint': 'indonesian',
        'summary': get_text_summary(text)
    }

def health_check() -> dict:
    """Health endpoint."""
    return {"ok": True, "module": "ilma_indonesian_nlp", "status": "operational"}

if __name__ == '__main__':
    test_text = "Saya mau membuat aplikasi web yang bagus dan cepat. Tolong bantu saya untuk optimasi performanya."
    
    print("="*60)
    print("ILMA Indonesian NLP Engine - Test")
    print("="*60)
    print(f"\nInput: {test_text}")
    print()
    
    result = analyze_text(test_text)
    print(f"Tokens: {result['token_count']}")
    print(f"Keywords: {result['keywords']}")
    print(f"Sentiment: {result['sentiment']['overall']}")
    print(f"Summary: {result['summary']}")
    
    print("\n[✅] Indonesian NLP operational")
