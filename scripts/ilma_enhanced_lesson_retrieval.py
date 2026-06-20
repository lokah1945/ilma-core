#!/usr/bin/env python3
"""
ILMA Phase 49-G: Enhanced Lesson Retrieval with Targeted Query Generation

Problem: Phase 48H canary used broad query "internal workflow optimization
evidence consistency lesson reuse" and got 0 results.

Solution: Auto-generate targeted queries from task intent, including:
- Task keywords
- Forbidden scope terms (from safety contract)
- Failure signature patterns
- Capability names
- Phase-specific bug classes
- Previous lesson IDs to avoid duplication
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.ilma_lesson_memory import LessonMemory
from scripts.ilma_runtime_router import RuntimeRouter, TaskClass

# === TAGGED LESSON SIGNATURES (for targeted retrieval) ===
TAGGED_SIGNATURES = {
    "parser_error": [
        "parser.parse_args() missing",
        "argparse error",
        "CLI broken"
    ],
    "scope_violation": [
        "external_publish in active",
        "dependency_install attempted",
        "forbidden scope executed",
        "scope check failed"
    ],
    "test_regression": [
        "test FAIL after patch",
        "pytest failed",
        "regression detected",
        "import broken"
    ],
    "weak_verified": [
        "evidence_id missing",
        "weak VERIFIED",
        "unverifiable claim",
        "no evidence_id"
    ],
    "lesson_empty": [
        "retrieval returned 0",
        "no lessons found",
        "empty retrieval result"
    ],
    "judge_fail": [
        "judge score below threshold",
        "FAIL status returned",
        "critic evaluation failed"
    ],
    "duplicate_lessons": [
        "duplicate lesson_id",
        "duplicate failure_signature",
        "dedup needed"
    ],
    "reuse_not_incremented": [
        "reuse_count not incremented",
        "mark_reused not called",
        "lesson reuse tracking broken"
    ],
    "trace_missing": [
        "trace not exported",
        "missing trace file",
        "trace schema incomplete"
    ],
    "runtime_router": [
        "routing decision wrong",
        "wrong workflow selected",
        "capability mismatch"
    ],
    "evidence_backfill": [
        "capability without evidence_id",
        "VERIFIED but no evidence",
        "backfill needed"
    ],
    "status_labeling": [
        "status label wrong",
        "PASS labeled as FAIL",
        "accuracy labeling issue"
    ],
    "external_publish": [
        "external_publish attempted",
        "forbidden publish scope",
        "unsafe operation blocked"
    ],
    "self_improvement": [
        "auto-learning loop failed",
        "optimization cycle broke",
        "evolution engine error"
    ]
}

# === FORBIDDEN SCOPE TERMS ===
FORBIDDEN_SCOPE_TERMS = [
    "dependency_install", "production_deployment", "destructive_delete",
    "os_build", "external_publish", "credential_use", "live_api_posting",
    "network_operation_risky", "mass_rewrite", "always_on"
]

# === CAPABILITY NAMES (for targeted search) ===
CAPABILITY_KEYWORDS = [
    "coding", "writing", "research", "audit", "planning", "security",
    "networking", "database", "api_integration", "messaging", "self_improve",
    "learning", "delegation", "orchestration", "evidence", "lesson"
]


class TargetedLessonRetrieval:
    """Enhanced lesson retrieval with targeted query generation"""
    
    def __init__(self):
        self.lm = LessonMemory()
        self.router = RuntimeRouter()
        self.phase_patterns = [
            "phase48", "phase49", "phase50",  # Phase-specific
            "evidence", "lesson", "retrieval", "canary",  # ILMA-specific
            "auto_learning", "self_improvement", "optimization"  # System-specific
        ]
    
    def generate_targeted_query(self, user_message: str, context: str = "") -> list:
        """Generate 3-5 targeted query strings from task + context"""
        queries = []
        
        # 1. Primary: task class keyword
        task_class, conf = self.router.classify_intent(user_message)
        queries.append(task_class.value)
        
        # 2. Secondary: intent keywords
        if conf > 0.5:
            # High confidence - use specific keywords
            words = user_message.lower().split()
            for word in words:
                if len(word) > 4 and word not in ['the', 'and', 'for', 'with']:
                    queries.append(word)
        
        # 3. Third: relevant capability names
        cap_map = {
            'code': ['coding', 'test', 'refactor', 'debug'],
            'write': ['writing', 'document', 'content'],
            'research': ['research', 'source', 'evidence'],
            'audit': ['audit', 'security', 'review', 'check'],
            'plan': ['planning', 'task', 'breakdown'],
            'internal': ['self_improve', 'learning', 'lesson', 'optimization'],
            'unsafe': FORBIDDEN_SCOPE_TERMS
        }
        queries.extend(cap_map.get(task_class.value, []))
        
        # 4. Fourth: if internal, add ILMA-specific terms
        if task_class == TaskClass.INTERNAL:
            queries.extend(["lesson", "retrieval", "evidence", "canary", "phase48"])
            queries.extend(FORBIDDEN_SCOPE_TERMS[:3])  # Top 3 forbidden
        
        # 5. Fifth: if related to failures, add failure signatures
        if any(fail in user_message.lower() for fail in ["error", "fail", "broken", "fix"]):
            queries.extend(["error", "fix", "broken", "patch"])
        
        # Deduplicate and limit to 5
        seen = set()
        unique_queries = []
        for q in queries:
            if q not in seen and len(q) > 2:
                seen.add(q)
                unique_queries.append(q)
        
        return unique_queries[:5]
    
    def search_with_targeting(self, user_message: str, context: str = "",
                              limit: int = 10) -> list:
        """Search for relevant lessons using targeted multi-query approach"""
        queries = self.generate_targeted_query(user_message, context)
        
        all_results = {}
        
        for query in queries:
            # Search with this specific query
            results = self.lm.search_lessons(query, limit=limit)
            
            for r in results:
                lid = r.get("lesson_id")
                if lid not in all_results:
                    all_results[lid] = r
        
        # Sort by relevance descending
        sorted_results = sorted(all_results.values(),
                              key=lambda x: x.get("relevance", 0),
                              reverse=True)
        
        return sorted_results[:limit]
    
    def search_for_internal_optimization(self, optimization_target: str,
                                         limit: int = 10) -> list:
        """Specialized search for internal optimization tasks"""
        # Build targeted query for optimization
        base_terms = ["self_improve", "optimization", "lesson", "retrieval"]
        
        # Add phase-specific patterns
        phase_terms = []
        for p in self.phase_patterns:
            if p in optimization_target.lower():
                phase_terms.append(p)
        
        # Add relevant signatures
        sig_terms = []
        for sig_type, sigs in TAGGED_SIGNATURES.items():
            for sig in sigs:
                if sig.lower() in optimization_target.lower():
                    sig_terms.append(sig_type)
        
        # Build final query list
        query_list = base_terms + phase_terms + sig_terms
        
        # Search
        all_results = {}
        for query in query_list[:8]:
            results = self.lm.search_lessons(query, limit=limit)
            for r in results:
                lid = r.get("lesson_id")
                if lid not in all_results:
                    all_results[lid] = r
        
        sorted_results = sorted(all_results.values(),
                              key=lambda x: x.get("relevance", 0),
                              reverse=True)
        
        return sorted_results[:limit]
    
    def search_for_forbidden_scope_check(self, task: str,
                                         limit: int = 5) -> list:
        """Check if task might trigger forbidden scope — retrieve safety lessons"""
        forbidden_terms = ["external", "publish", "deploy", "install", "delete",
                          "credential", "api_posting", "always_on", "mass_rewrite"]
        
        task_lower = task.lower()
        triggered = [t for t in forbidden_terms if t in task_lower]
        
        if not triggered:
            return []
        
        # Get safety-related lessons
        all_results = {}
        for term in triggered[:3]:
            results = self.lm.search_lessons(term, limit=limit)
            for r in results:
                lid = r.get("lesson_id")
                if lid not in all_results:
                    all_results[lid] = r
        
        sorted_results = sorted(all_results.values(),
                              key=lambda x: x.get("relevance", 0),
                              reverse=True)
        
        return sorted_results[:limit]
    
    def verify_retrieval_non_empty(self, query: str, min_results: int = 1) -> bool:
        """Verify that a query returns at least min_results"""
        results = self.lm.search_lessons(query, limit=min_results + 1)
        return len(results) >= min_results


def demo():
    """Test targeted retrieval vs Phase 48H broad query"""
    tlr = TargetedLessonRetrieval()
    
    print("=" * 60)
    print("Phase 49-G: Targeted Lesson Retrieval Demo")
    print("=" * 60)
    
    # Test 1: Phase 48H problem case
    print("\n1. Phase 48H Problem: Internal optimization")
    print("   Old broad query: 'internal workflow optimization evidence consistency lesson reuse'")
    old_results = tlr.lm.search_lessons("internal workflow optimization evidence consistency lesson reuse", limit=5)
    print(f"   Old results: {len(old_results)} (Phase 48H got 0)")
    
    # New targeted query
    queries = tlr.generate_targeted_query("optimize ILMA's routing policy")
    print(f"   New queries: {queries}")
    new_results = tlr.search_with_targeting("optimize ILMA's routing policy")
    print(f"   New results: {len(new_results)}")
    
    if new_results:
        print(f"   Top result: {new_results[0].get('lesson_id', 'unknown')[:8]}... | "
              f"sig: {new_results[0].get('failure_signature', 'none')[:40]}...")
    
    # Test 2: Safe vs unsafe
    print("\n2. Forbidden scope check")
    unsafe_task = "publish my changes to external API"
    safety_lessons = tlr.search_for_forbidden_scope_check(unsafe_task)
    print(f"   Unsafe task: '{unsafe_task}'")
    print(f"   Safety lessons: {len(safety_lessons)}")
    
    # Test 3: Internal optimization specialized
    print("\n3. Internal optimization specialized search")
    opt_results = tlr.search_for_internal_optimization("fix evidence backfill in capability registry")
    print(f"   Optimization: 'fix evidence backfill in capability registry'")
    print(f"   Results: {len(opt_results)}")
    for r in opt_results[:3]:
        print(f"   - {r.get('lesson_id','?')[:8]} | {r.get('relevance',0):.2f} | {r.get('failure_signature','?')[:50]}")
    
    # Test 4: Verify non-empty
    print("\n4. Query verification (non-empty check)")
    test_queries = ["parser", "external_publish", "lesson", "evidence", "routing"]
    for q in test_queries:
        non_empty = tlr.verify_retrieval_non_empty(q)
        count_results = len(tlr.lm.search_lessons(q, limit=10))
        print(f"   '{q}': non_empty={non_empty}, count={count_results}")


if __name__ == "__main__":
    demo()