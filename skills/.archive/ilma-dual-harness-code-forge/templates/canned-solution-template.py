"""
Canned Solutions Template for ILMA Generator Harness
====================================================

Use this template to add new canned test solutions for E2E testing the
Dual-Harness Code Forge WITHOUT a live LLM call.

Each canned solution is keyed by task_id. When a test invokes the forge
with a known task_id, the generator returns this code instead of calling
an LLM. This lets you:
- Smoke-test the full 5-tier pipeline (generate → review → validate → arbitrate → record)
- Verify arbiter scoring without API costs
- Demonstrate the architecture to stakeholders

To add a new canned solution:
1. Choose a unique task_id (e.g. "binary_search", "merge_sort")
2. Write the canonical Python solution
3. Write a 1-sentence rationale (focus on the algorithm/structure choice)
4. List 3-5 test cases that should pass
5. Add to the CANNED dict in ilma_generator_harness.py

Format for each entry:
    task_id: (code, rationale, [test1, test2, test3])

Where:
- code: Complete, runnable Python (including imports)
- rationale: One sentence explaining the design choice
- tests: List of test case names that the validator will run

The validator's _run_tests method must have a matching branch for the
task_id. If the task_id is not in the validator's switch, the test will
fall through to the generic "import + exec" test (which only verifies
the code imports cleanly, not that it's correct).

Example entries follow.
"""

# Example 1: Binary search
BINARY_SEARCH = (
    "from typing import List\n\n"
    "def binary_search(arr: List[int], target: int) -> int:\n"
    "    \"\"\"Return index of target in sorted arr, or -1 if absent.\"\"\"\n"
    "    left, right = 0, len(arr) - 1\n"
    "    while left <= right:\n"
    "        mid = (left + right) // 2\n"
    "        if arr[mid] == target:\n"
    "            return mid\n"
    "        elif arr[mid] < target:\n"
    "            left = mid + 1\n"
    "        else:\n"
    "            right = mid - 1\n"
    "    return -1\n",
    "Classic iterative binary search with O(log n) time, O(1) space, no recursion.",
    ["test_found", "test_not_found", "test_empty_array", "test_single_element"]
)

# Example 2: Merge sort
MERGE_SORT = (
    "from typing import List\n\n"
    "def merge_sort(arr: List[int]) -> List[int]:\n"
    "    if len(arr) <= 1:\n"
    "        return arr\n"
    "    mid = len(arr) // 2\n"
    "    left = merge_sort(arr[:mid])\n"
    "    right = merge_sort(arr[mid:])\n"
    "    return _merge(left, right)\n\n"
    "def _merge(left: List[int], right: List[int]) -> List[int]:\n"
    "    result = []\n"
    "    i = j = 0\n"
    "    while i < len(left) and j < len(right):\n"
    "        if left[i] <= right[j]:\n"
    "            result.append(left[i])\n"
    "            i += 1\n"
    "        else:\n"
    "            result.append(right[j])\n"
    "            j += 1\n"
    "    result.extend(left[i:])\n"
    "    result.extend(right[j:])\n"
    "    return result\n",
    "Recursive merge sort with O(n log n) time, O(n) space, stable sort.",
    ["test_basic", "test_empty", "test_single", "test_sorted", "test_reverse"]
)

# Example 3: LRU cache (already in main code as 'lru_cache', but illustrates the pattern)
# Note: This is just a template — actual canned solutions live in ilma_generator_harness.py

CANNED_TEMPLATES = {
    "binary_search": BINARY_SEARCH,
    "merge_sort": MERGE_SORT,
}


# Validator test branches that should accompany each canned solution:

BINARY_SEARCH_VALIDATOR_TESTS = """
        elif solution.task_id == "binary_search":
            try:
                ns = {}
                exec(solution.code, ns)
                fn = ns.get("binary_search")
                if fn is None:
                    return [{"test": "import", "passed": False, "error": "no binary_search function"}], 0.0
                cases = [
                    ("test_found", [1, 3, 5, 7, 9], 5, 2),
                    ("test_not_found", [1, 3, 5, 7, 9], 4, -1),
                    ("test_empty_array", [], 5, -1),
                    ("test_single_element", [42], 42, 0),
                ]
                total = 0
                passed = 0
                for name, arr, target, expected in cases:
                    total += 1
                    try:
                        result = fn(arr, target)
                        if result == expected:
                            passed += 1
                            results.append({"test": name, "passed": True})
                        else:
                            results.append({"test": name, "passed": False,
                                            "expected": expected, "actual": result})
                    except Exception as e:
                        results.append({"test": name, "passed": False, "error": str(e)})
            except Exception as e:
                return [{"test": "exec", "passed": False, "error": str(e)}], 0.0
"""

MERGE_SORT_VALIDATOR_TESTS = """
        elif solution.task_id == "merge_sort":
            try:
                ns = {}
                exec(solution.code, ns)
                fn = ns.get("merge_sort")
                if fn is None:
                    return [{"test": "import", "passed": False, "error": "no merge_sort function"}], 0.0
                cases = [
                    ("test_basic", [3, 1, 4, 1, 5, 9, 2, 6], [1, 1, 2, 3, 4, 5, 6, 9]),
                    ("test_empty", [], []),
                    ("test_single", [42], [42]),
                    ("test_sorted", [1, 2, 3, 4, 5], [1, 2, 3, 4, 5]),
                    ("test_reverse", [5, 4, 3, 2, 1], [1, 2, 3, 4, 5]),
                ]
                total = 0
                passed = 0
                for name, arr, expected in cases:
                    total += 1
                    try:
                        result = fn(arr)
                        if result == expected:
                            passed += 1
                            results.append({"test": name, "passed": True})
                        else:
                            results.append({"test": name, "passed": False,
                                            "expected": expected, "actual": result})
                    except Exception as e:
                        results.append({"test": name, "passed": False, "error": str(e)})
            except Exception as e:
                return [{"test": "exec", "passed": False, "error": str(e)}], 0.0
"""


# Anti-patterns (DO NOT DO)
#
# 1. Don't return trivially wrong solutions to "test the reviewer". The arbiter
#    will mark them as failing tests, and you'll learn nothing about the architecture.
#
# 2. Don't include network calls in canned solutions. The validator's exec() runs
#    them in a sandbox without network. urllib.request.urlopen will hang.
#
# 3. Don't include file I/O unless you mock it. open() will fail or pollute
#    the working directory.
#
# 4. Don't include time.sleep() or any blocking call. Slows E2E tests.
#
# 5. Don't use external packages (numpy, pandas, etc.). The validator imports
#    them in a clean environment; failures will be spurious.

# When to add new canned solutions
#
# - When you build a new test category (e.g., sorting, graph algorithms)
# - When you want to demo the forge to stakeholders
# - When you need regression tests for the validator's _run_tests branch
#
# When NOT to add canned solutions
#
# - For real production tasks (canned solutions are for testing only)
# - When the test would be better served by a real LLM call (real-world scenarios)
# - When the solution is trivial (1-line functions don't demonstrate the 5-tier pipeline)
