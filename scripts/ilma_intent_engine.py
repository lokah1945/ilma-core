#!/usr/bin/env python3
"""
ILMA Intent Engine v1.0
========================
Intent recognition and routing engine for ILMA.

Analyzes user intent and routes to appropriate capabilities.
"""
import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict

WORKSPACE = Path("/root/.hermes/profiles/ilma")

# ============================================================================
# INTENT PATTERNS
# ============================================================================

INTENT_PATTERNS = {
    "greeting": {
        "patterns": [r"halo", r"hai", r"hi", r"hello", r"pagi", r"siang", r"sore", r"malam", r"hay"],
        "responses": ["Halo! Ada yang bisa saya bantu?", "Hai! Saya ILMA, ada yang bisa协助?"],
        "priority": 1
    },
    "create": {
        "patterns": [r"buat", r"create", r"generate", r"buatlah", r"buatkan"],
        "responses": ["Baik, saya akan membuat untuk Anda."],
        "priority": 8
    },
    "delete": {
        "patterns": [r"hapus", r"delete", r"remove", r"buang"],
        "responses": ["Menghapus sesuai permintaan..."],
        "priority": 9
    },
    "read": {
        "patterns": [r"baca", r"read", r"lihat", r"tampilkan", r"show", r"cari", r"search"],
        "responses": ["Baik, saya akan mencarikan informasi tersebut."],
        "priority": 7
    },
    "update": {
        "patterns": [r"ubah", r"update", r"edit", r"modif", r"rubah"],
        "responses": ["Baik, saya akan memperbarui."],
        "priority": 8
    },
    "explain": {
        "patterns": [r"jelaskan", r"explain", r"apa itu", r"apa kegunaan", r"apa maksud"],
        "responses": ["Berikut penjelasannya:"],
        "priority": 5
    },
    "help": {
        "patterns": [r"tolong", r"bantu", r"help", r"ask", r"tolongan", r"panduan"],
        "responses": ["Saya siap membantu!"],
        "priority": 3
    },
    "code": {
        "patterns": [r"kode", r"code", r"coding", r"program", r"script", r"function"],
        "responses": ["Baik, saya akan membantu dengan kode."],
        "priority": 8
    },
    "research": {
        "patterns": [r"riset", r"research", r"pelajari", r"analisis", r"study"],
        "responses": ["Saya akan melakukan riset untuk Anda."],
        "priority": 7
    },
    "planning": {
        "patterns": [r"rencana", r"plan", r"planning", r"strategi", r"roadmap"],
        "responses": ["Baik, saya akan membantu perencanaan."],
        "priority": 6
    },
    "question": {
        "patterns": [r"\?$", r"apa", r"siapa", r"dimana", r"kapan", r"mengapa", r"how", r"what", r"who", r"where", r"when", r"why"],
        "responses": ["Berikut jawabannya:"],
        "priority": 5
    },
    "task": {
        "patterns": [r"kerjakan", r"eksekusi", r"execute", r"run", r"jalankan", r"kerjakan"],
        "responses": ["Baik, saya akan mengeksekusi tugas tersebut."],
        "priority": 9
    },
    "status": {
        "patterns": [r"status", r"kondisi", r"health", r"sehat"],
        "responses": ["Berikut status terkini:"],
        "priority": 4
    },
    "report": {
        "patterns": [r"laporan", r"report", r"hasil", r"summary"],
        "responses": ["Berikut laporan yang diminta:"],
        "priority": 5
    },
    "learn": {
        "patterns": [r"belajar", r"learn", r"pelajari", r"evolve", r"berkembang"],
        "responses": ["Baik, saya akan belajar dari ini."],
        "priority": 8
    },
    "improve": {
        "patterns": [r"perbaiki", r"improve", r"upgrade", r"optimize", r"tingkatkan"],
        "responses": ["Baik, saya akan mengoptimalkan."],
        "priority": 8
    },
    "security": {
        "patterns": [r"security", r"keamanan", r"aman", r"protect", r"lindungi"],
        "responses": ["Saya akan melakukan проверка keamanan."],
        "priority": 9
    },
    "data": {
        "patterns": [r"data", r"database", r"db", r"tabel", r"table"],
        "responses": ["Baik, saya akan mengolah data tersebut."],
        "priority": 7
    },
    "network": {
        "patterns": [r"network", r"jaringan", r"server", r"api", r"endpoint"],
        "responses": ["Baik, saya akan检查 jaringan."],
        "priority": 7
    },
    "deploy": {
        "patterns": [r"deploy", r"deployment", r"rilis", r"release"],
        "responses": ["Baik, saya akan melakukan deployment."],
        "priority": 9
    }
}

# ============================================================================
# ENTITY EXTRACTOR
# ============================================================================

class EntityExtractor:
    """Extract entities from text."""
    
    @staticmethod
    def extract_code_languages(text: str) -> List[str]:
        """Extract programming languages mentioned."""
        languages = ["python", "javascript", "js", "java", "c++", "c#", "ruby", "go", "rust", "php", "swift", "kotlin", "typescript", "bash", "shell", "sql", "html", "css", "react", "vue", "angular", "node", "nodejs", "django", "flask", "fastapi", "laravel"]
        found = []
        text_lower = text.lower()
        for lang in languages:
            if lang in text_lower:
                found.append(lang)
        return found
    
    @staticmethod
    def extract_file_types(text: str) -> List[str]:
        """Extract file types mentioned."""
        types = ["py", "js", "ts", "json", "yaml", "yml", "xml", "md", "txt", "csv", "html", "css", "sql", "sh", "bash"]
        found = []
        text_lower = text.lower()
        for t in types:
            if f".{t}" in text_lower or f"{t} file" in text_lower:
                found.append(t)
        return found
    
    @staticmethod
    def extract_numbers(text: str) -> List[int]:
        """Extract numbers from text."""
        return [int(n) for n in re.findall(r"\d+", text)]
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract URLs from text."""
        return re.findall(r"https?://[^\s]+", text)
    
    @staticmethod
    def extract_entities(text: str) -> Dict:
        """Extract all entities from text."""
        return {
            "languages": EntityExtractor.extract_code_languages(text),
            "file_types": EntityExtractor.extract_file_types(text),
            "numbers": EntityExtractor.extract_numbers(text),
            "urls": EntityExtractor.extract_urls(text),
            "has_question": "?" in text,
            "has_code_block": "```" in text or "```" in text
        }


# ============================================================================
# INTENT ENGINE
# ============================================================================

class IntentEngine:
    """
    Main intent recognition engine.
    Analyzes user input and determines intent with confidence.
    """
    
    def __init__(self):
        self.patterns = INTENT_PATTERNS
        self.history = []
        self.context_stack = []
    
    def recognize(self, text: str) -> Dict:
        """
        Recognize intent from text.
        
        Returns:
            Dict with intent, confidence, entities, and suggested actions
        """
        text_lower = text.lower()
        
        # Score each intent
        scored = {}
        for intent_name, intent_data in self.patterns.items():
            score = 0
            matched_patterns = []
            
            for pattern in intent_data["patterns"]:
                if re.search(pattern, text_lower):
                    score += 1
                    matched_patterns.append(pattern)
            
            if score > 0:
                # Normalize by pattern count
                normalized_score = score / len(intent_data["patterns"])
                # Boost by priority
                priority_boost = intent_data["priority"] / 10
                final_score = min(1.0, normalized_score + priority_boost * 0.2)
                
                scored[intent_name] = {
                    "score": final_score,
                    "matched_patterns": matched_patterns,
                    "priority": intent_data["priority"]
                }
        
        # Sort by score
        sorted_intents = sorted(scored.items(), key=lambda x: x[1]["score"], reverse=True)
        
        # Extract entities
        entities = EntityExtractor.extract_entities(text)
        
        # Build result
        if sorted_intents:
            top_intent = sorted_intents[0]
            result = {
                "text": text,
                "primary_intent": top_intent[0],
                "confidence": top_intent[1]["score"],
                "all_intents": [(name, data["score"]) for name, data in sorted_intents[:5]],
                "entities": entities,
                "response": top_intent[1].get("matched_patterns", [""])[0] if sorted_intents else None,
                "priority": self.patterns.get(top_intent[0], {}).get("priority", 5)
            }
        else:
            result = {
                "text": text,
                "primary_intent": "unknown",
                "confidence": 0.0,
                "all_intents": [],
                "entities": entities,
                "response": None,
                "priority": 5
            }
        
        # Add to history
        self.history.append(result)
        
        return result
    
    def get_suggested_actions(self, intent: str, entities: Dict) -> List[Dict]:
        """Get suggested actions based on intent and entities."""
        actions = []
        
        if intent == "code":
            if entities.get("languages"):
                for lang in entities["languages"]:
                    actions.append({
                        "type": "generate_code",
                        "language": lang,
                        "priority": "high"
                    })
            else:
                actions.append({
                    "type": "generate_code",
                    "language": "python",
                    "priority": "normal"
                })
        
        elif intent == "create":
            if entities.get("file_types"):
                actions.append({
                    "type": "create_file",
                    "file_type": entities["file_types"][0],
                    "priority": "high"
                })
        
        elif intent == "read":
            if entities.get("urls"):
                actions.append({
                    "type": "fetch_url",
                    "url": entities["urls"][0],
                    "priority": "high"
                })
            else:
                actions.append({
                    "type": "search",
                    "priority": "normal"
                })
        
        elif intent == "task":
            actions.append({
                "type": "execute_task",
                "priority": "high"
            })
        
        elif intent == "explain":
            actions.append({
                "type": "explain",
                "priority": "normal"
            })
        
        elif intent == "learn" or intent == "improve":
            actions.append({
                "type": "run_evolution",
                "priority": "high"
            })
        
        elif intent == "security":
            actions.append({
                "type": "run_security_check",
                "priority": "high"
            })
        
        elif intent == "deploy":
            actions.append({
                "type": "run_deployment",
                "priority": "high"
            })
        
        return actions
    
    def push_context(self, intent: str, data: Dict = None):
        """Push context to stack."""
        self.context_stack.append({
            "intent": intent,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep stack limited
        if len(self.context_stack) > 10:
            self.context_stack = self.context_stack[-10:]
    
    def pop_context(self) -> Optional[Dict]:
        """Pop context from stack."""
        if self.context_stack:
            return self.context_stack.pop()
        return None
    
    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get recognition history."""
        return self.history[-limit:]


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Intent Engine")
    parser.add_argument("command", nargs="?", default="recognize",
                        choices=["recognize", "entities", "actions", "history", "test"])
    parser.add_argument("--text", type=str, help="Text to analyze")
    parser.add_argument("--intent", type=str, help="Intent for actions")
    parser.add_argument("--limit", type=int, default=10, help="History limit")
    
    engine = IntentEngine()
    args = parser.parse_args()
    
    if args.command == "recognize":
        if not args.text:
            # Interactive mode
            print("Enter text to analyze (Ctrl+C to exit):")
            while True:
                try:
                    text = input("> ")
                    result = engine.recognize(text)
                    print(json.dumps(result, indent=2))
                    print()
                except KeyboardInterrupt:
                    break
        else:
            result = engine.recognize(args.text)
            print(json.dumps(result, indent=2))
    
    elif args.command == "entities":
        if not args.text:
            print("Error: --text required")
            sys.exit(1)
        
        entities = EntityExtractor.extract_entities(args.text)
        print(json.dumps(entities, indent=2))
    
    elif args.command == "actions":
        if not args.intent:
            print("Error: --intent required")
            sys.exit(1)
        
        entities = {}
        if args.text:
            entities = EntityExtractor.extract_entities(args.text)
        
        actions = engine.get_suggested_actions(args.intent, entities)
        print(json.dumps(actions, indent=2))
    
    elif args.command == "history":
        history = engine.get_history(args.limit)
        print(f"Recent {len(history)} recognitions:")
        for h in history:
            print(f"  [{h['primary_intent']}] ({h['confidence']:.2f}) {h['text'][:50]}...")
    
    elif args.command == "test":
        # Run test recognitions
        test_texts = [
            "Halo, apa kabar?",
            "Buatkan saya script Python untuk menghitung factorial",
            "Jelaskan apa itu machine learning",
            "Hapus semua file log di folder /tmp",
            "Cari informasi tentang AI agents",
            "Tolong bantu saya coding",
            "Lakukan security audit",
            "Deploy aplikasi ke server",
            "Apa itu REST API?",
            "Buatkan rencana project untuk next month"
        ]
        
        print("Running intent recognition tests...")
        print("=" * 60)
        
        for text in test_texts:
            result = engine.recognize(text)
            print(f"Text: {text}")
            print(f"Intent: {result['primary_intent']} (confidence: {result['confidence']:.2f})")
            print(f"Entities: {result['entities']}")
            print("-" * 60)

if __name__ == "__main__":
    main()
