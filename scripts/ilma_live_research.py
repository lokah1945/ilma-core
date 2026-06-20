#!/usr/bin/env python3
"""
ILMA Live Research Module v1.0
==============================
Live research when internal knowledge (lesson memory) is insufficient.

Triggers when:
1. Reflection fails to find root cause
2. Repeated failure across iterations
3. Unknown error (不在 lesson memory)
4. Error contains novel pattern not in database

Sources:
- Web search (DuckDuckGo, Bing via WebSearcher)
- arXiv papers (via arxiv skill pattern)
- Felo search (if available)

Usage:
    from scripts.ilma_live_research import LiveResearch
    lr = LiveResearch()
    results = lr.research(error_context="ModuleNotFoundError: No module named 'torch'", task_type="code")
    # results = {solutions: [], papers: [], confidence: 0.0-1.0, new_knowledge: [...]}
"""

from __future__ import annotations

import json
import re
import time
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE


@dataclass
class ResearchResult:
    """Result from live research."""
    solutions: List[str]          # Potential solutions found
    papers: List[Dict]           # Relevant papers (title, url, abstract)
    confidence: float            # 0.0-1.0 confidence in solutions
    new_knowledge: List[str]    # New learnings to store as lesson
    sources: List[str]          # Source URLs
    research_duration: float     # Seconds spent researching

    def to_dict(self) -> Dict[str, Any]:
        return {
            "solutions": self.solutions,
            "papers": self.papers,
            "confidence": self.confidence,
            "new_knowledge": self.new_knowledge,
            "sources": self.sources,
            "research_duration": self.research_duration
        }


class LiveResearch:
    """
    Live research module - activates when internal knowledge insufficient.
    
    Designed for:
    - Novel errors not in lesson memory
    - Repeated failures across iterations
    - Unclear root cause from reflection
    """

    def __init__(self):
        self.cache_dir = WORKSPACE / ".cache" / "live_research"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = 1800  # 30 minutes
        
        # Web search providers (fallback chain)
        self.search_providers = ["duckduckgo", "bing"]
        
        # Known error patterns (cached from previous research)
        self.known_patterns_cache = self._load_known_patterns()

    def research(
        self,
        error_context: str,
        task_type: str = "code",
        root_cause: str = "",
        failed_attempts: int = 0,
        max_duration: float = 30.0
    ) -> ResearchResult:
        """
        Perform live research on error/problem.
        
        Args:
            error_context: The error message or problem description
            task_type: Type of task (code, writing, analysis, etc.)
            root_cause: What reflection identified (if any)
            failed_attempts: Number of failed attempts so far
            max_duration: Maximum seconds to spend researching
            
        Returns:
            ResearchResult with solutions, papers, new knowledge
        """
        start_time = time.time()
        
        print(f"\n🧪 [LIVE RESEARCH] Starting research on: {error_context[:100]}")
        
        solutions = []
        papers = []
        sources = []
        new_knowledge = []
        
        # Step 1: Build search queries from error context
        queries = self._build_queries(error_context, task_type, root_cause)
        
        # Step 2: Web search for solutions
        web_results = self._search_web(queries, max_duration - (time.time() - start_time))
        solutions.extend(web_results.get("solutions", []))
        sources.extend(web_results.get("sources", []))
        
        # Step 3: Search arXiv for relevant papers (if code/technical task)
        if task_type in ("code", "analysis", "planning") and time.time() - start_time < max_duration - 10:
            arxiv_results = self._search_arxiv(queries, max_duration - (time.time() - start_time))
            papers.extend(arxiv_results.get("papers", []))
            sources.extend(arxiv_results.get("sources", []))
        
        # Step 4: Check known patterns cache
        cached_solutions = self._check_known_patterns(error_context)
        if cached_solutions:
            solutions.extend(cached_solutions)
            print(f"   📚 Found {len(cached_solutions)} solutions from known patterns cache")
        
        # Step 5: Deduplicate and score
        solutions = list(dict.fromkeys(solutions))[:10]  # Deduplicate, keep top 10
        
        # Calculate confidence based on sources found
        confidence = min(1.0, (len(solutions) * 0.15) + (len(papers) * 0.2) + (0.1 if cached_solutions else 0))
        
        # Step 6: Generate new knowledge entries
        if solutions:
            new_knowledge = [
                f"Error pattern: {error_context[:80]}",
                f"Solution: {solutions[0] if solutions else 'No solution found'}",
                f"Root cause: {root_cause[:80] if root_cause else 'Unknown'}"
            ]
        
        research_duration = time.time() - start_time
        
        print(f"   ✅ Research complete: {len(solutions)} solutions, {len(papers)} papers, confidence={confidence:.2f} in {research_duration:.1f}s")
        
        return ResearchResult(
            solutions=solutions,
            papers=papers,
            confidence=confidence,
            new_knowledge=new_knowledge,
            sources=sources,
            research_duration=research_duration
        )

    def _build_queries(self, error_context: str, task_type: str, root_cause: str) -> List[str]:
        """Build search queries from error context."""
        queries = []
        
        # Extract key terms from error
        error_terms = re.findall(r'[A-Z][a-z]+Error|ModuleNotFoundError|ImportError|\w+NotDefined|[a-z_]+ exception', error_context)
        
        # Build queries based on error type
        if 'ModuleNotFoundError' in error_context or 'No module named' in error_context:
            # Missing dependency - search for installation/alternative
            match = re.search(r"No module named '([^']+)'", error_context)
            if match:
                module = match.group(1)
                queries.append(f"python {module} module not found install alternative")
                queries.append(f"how to install {module} python")
        elif 'ImportError' in error_context:
            queries.append(f"python ImportError {error_context[:50]} solution")
        elif 'Permission' in error_context or 'Access' in error_context:
            queries.append(f"linux permission denied fix {task_type}")
        elif root_cause and 'unknown' in root_cause.lower():
            # Unknown root cause - search broadly
            queries.append(f"{task_type} error {error_context[:60]} solution")
            queries.append(f"{error_context[:40]} troubleshooting")
        else:
            # General query
            queries.append(f"{error_context[:80]}")
        
        # Add task-specific queries
        if task_type == "code":
            queries.append(f"python programming error {error_context[:50]} fix")
        elif task_type == "writing":
            queries.append(f"writing error {error_context[:50]} solution")
        elif task_type == "analysis":
            queries.append(f"data analysis error {error_context[:50]} fix")
        
        return queries[:4]  # Limit to 4 queries max

    def _search_web(self, queries: List[str], max_time: float) -> Dict[str, Any]:
        """Search the web for solutions using FELO FREE (primary) + fallback."""
        results = {"solutions": [], "sources": []}
        
        if not queries:
            return results
        
        # === PRIMARY: Use FELO FREE native_search (100% FREE, no API key) ===
        try:
            import sys
            sys.path.insert(0, '/root/.hermes/profiles/ilma/scripts')
            from ilma_felo_free import native_search as felo_native_search
            
            for query in queries:
                try:
                    search_result = felo_native_search(query, limit=5)
                    
                    if search_result.get("status") == "ok":
                        for r in search_result.get("results", []):
                            snippet = r.get("snippet", "")
                            title = r.get("title", "")
                            # Extract actionable solution
                            solution = self._extract_solution(snippet, title)
                            if solution:
                                results["solutions"].append(solution)
                            results["sources"].append(r.get("url", ""))
                        
                        print(f"   ✅ FELO FREE found {len(search_result.get('results', []))} results")
                        
                        if results["solutions"]:
                            break  # Got results, move to next query
                    else:
                        print(f"   ⚠️ FELO FREE returned non-ok status: {search_result.get('status')}")
                        
                except Exception as e:
                    print(f"   ⚠️ FELO FREE search failed for '{query}': {e}")
                    continue
                    
        except ImportError as e:
            print(f"   ⚠️ FELO FREE module not available: {e}")
            # Fallback to direct requests
            results = self._search_web_fallback(queries)
        
        return results

    def _search_web_fallback(self, queries: List[str]) -> Dict[str, Any]:
        """Fallback web search using requests directly."""
        results = {"solutions": [], "sources": []}
        
        for query in queries:
            for name, base_url in [
                ("duckduckgo", "https://html.duckduckgo.com/html/?q="),
                ("startpage", "https://www.startpage.com/do/search?q="),
                ("mojeek", "https://www.mojeek.com/search?q="),
            ]:
                try:
                    import urllib.parse
                    url = base_url + urllib.parse.quote(query)
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                    resp = requests.get(url, headers=headers, timeout=8, verify=False)
                    
                    if resp.status_code == 200:
                        # Extract snippets based on search engine
                        if 'duckduckgo' in url:
                            snippets = re.findall(r'<a class="result__snippet"[^>]*>([^<]+)</a>', resp.text)
                        elif 'startpage' in url:
                            snippets = re.findall(r'<p class="desc">([^<]+)</p>', resp.text)
                        elif 'mojeek' in url:
                            snippets = re.findall(r'<p class="s-desc">([^<]+)</p>', resp.text)
                        else:
                            snippets = re.findall(r'snippet[^>]*>([^<]+)', resp.text)
                        
                        for s in snippets[:3]:
                            clean = re.sub(r'<[^>]+>', '', s).strip()
                            if clean and len(clean) > 20:
                                results["solutions"].append(clean)
                                results["sources"].append(f"{name}: {query[:30]}")
                        
                        if results["solutions"]:
                            break  # Got results, move to next query
                except Exception as e:
                    continue
        
        return results

    def _search_arxiv(self, queries: List[str], max_time: float) -> Dict[str, Any]:
        """Search arXiv for relevant papers."""
        results = {"papers": [], "sources": []}
        
        if max_time < 5:
            return results
        
        for query in queries[:2]:  # Limit to 2 arxiv queries
            try:
                # Search arXiv API
                arxiv_url = "http://export.arxiv.org/api/query"
                params = {
                    "search_query": f"all:{query[:50]}",
                    "start": 0,
                    "max_results": 3
                }
                resp = requests.get(arxiv_url, params=params, timeout=15)
                
                if resp.status_code == 200:
                    # ParseAtom feed
                    entries = re.findall(r'<entry>(.*?)</entry>', resp.text, re.DOTALL)
                    for entry in entries[:2]:
                        title = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
                        summary = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
                        link = re.search(r'<id>(.*?)</id>', entry)
                        
                        if title:
                            paper = {
                                "title": title.group(1).strip().replace('\n', ' '),
                                "abstract": summary.group(1).strip()[:300] if summary else "",
                                "url": link.group(1).strip() if link else ""
                            }
                            results["papers"].append(paper)
                            results["sources"].append(paper["url"])
            except Exception as e:
                print(f"   ⚠️ arXiv search failed: {e}")
                continue
        
        return results

    def _extract_solution(self, snippet: str, title: str) -> Optional[str]:
        """Extract actionable solution from search snippet."""
        # Look for solution patterns
        solution_patterns = [
            r'(?:try|use|install|run|execute)\s+[`"]?([^\s`"]+)[`"]?',
            r'(?:fix|solution|answer):\s*([^.!?]+)',
            r'(?:step|do)\s+\d+[:\s]+([^.!?]+)',
        ]
        
        for pattern in solution_patterns:
            match = re.search(pattern, snippet, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
        
        # If no pattern, use title as solution hint
        if title and len(title) > 10:
            return f"Solution hint: {title[:150]}"
        
        return None

    def _check_known_patterns(self, error_context: str) -> List[str]:
        """Check if we have known solutions for this error pattern."""
        solutions = []
        
        for pattern, known in self.known_patterns_cache.items():
            if pattern.lower() in error_context.lower():
                solutions.extend(known.get("solutions", [])[:3])
        
        return solutions

    def _load_known_patterns(self) -> Dict[str, Dict]:
        """Load known error patterns from cache."""
        cache_file = self.cache_dir / "known_patterns.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def store_research_result(self, error_context: str, result: ResearchResult):
        """Store research result for future use."""
        cache_file = self.cache_dir / "known_patterns.json"
        
        # Load existing patterns
        patterns = self._load_known_patterns()
        
        # Extract short pattern key
        pattern_key = error_context[:60]
        
        # Store with solutions
        patterns[pattern_key] = {
            "solutions": result.solutions[:5],
            "confidence": result.confidence,
            "timestamp": time.time(),
            "sources": result.sources[:5]
        }
        
        # Save back
        try:
            with open(cache_file, 'w') as f:
                json.dump(patterns, f, indent=2)
            print(f"   💾 Stored research result for pattern: {pattern_key[:40]}")
        except Exception as e:
            print(f"   ⚠️ Failed to store research result: {e}")

    def should_research(
        self,
        failed_attempts: int,
        root_cause: str,
        has_lesson_memory: bool,
        confidence: float = 0.0
    ) -> Tuple[bool, str]:
        """
        Determine if live research should be triggered.
        
        Returns:
            (should_research, reason)
        """
        # Trigger if:
        # 1. Failed attempts >= 3 and no clear solution
        if failed_attempts >= 3 and (not root_cause or "unknown" in root_cause.lower()):
            return True, f"Repeated failures ({failed_attempts}x) with unclear root cause"
        
        # 2. No lesson memory found AND uncertain
        if not has_lesson_memory and confidence < 0.3:
            return True, "No lesson memory and low confidence"
        
        # 3. Unknown/uncertain root cause
        if root_cause and ("unknown" in root_cause.lower() or "unclear" in root_cause.lower()):
            if failed_attempts >= 2:
                return True, f"Unclear root cause after {failed_attempts} attempts"
        
        # 4. Novel error pattern (not in known patterns)
        known_patterns = self._load_known_patterns()
        is_novel = not any(p.lower() in root_cause.lower() for p in known_patterns.keys() if root_cause)
        if is_novel and failed_attempts >= 2:
            return True, "Novel error pattern not in known patterns"
        
        return False, "No research needed"


# Standalone test
if __name__ == "__main__":
    lr = LiveResearch()
    
    # Test research on a sample error
    result = lr.research(
        error_context="ModuleNotFoundError: No module named 'numpy'",
        task_type="code",
        root_cause="",
        failed_attempts=2
    )
    
    print("\n=== RESEARCH RESULT ===")
    print(f"Solutions: {len(result.solutions)}")
    for s in result.solutions[:3]:
        print(f"  - {s}")
    print(f"Confidence: {result.confidence}")
    print(f"Duration: {result.research_duration:.1f}s")
    
    # Test should_research
    should, reason = lr.should_research(
        failed_attempts=3,
        root_cause="unknown",
        has_lesson_memory=False
    )
    print(f"\nShould research: {should} ({reason})")