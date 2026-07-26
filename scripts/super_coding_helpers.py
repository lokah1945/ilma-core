#!/usr/bin/env python3
"""
ILMA Super Coding Helpers — Performance utilities for heavy coding tasks
Auto-loadable in execute_code sessions.

Environment: 16-core Xeon E5-2665, 2.8GB RAM, NO AVX2
Working libraries: numpy 2.4.4, numba 0.65.0, scipy 1.17.1, joblib 1.5.3, rapidfuzz 3.14.5
"""
import os
import gc
import csv

# ============================================================
# Imports — standard header for heavy coding
# ============================================================
import numpy as np
from numba import jit, prange

# ============================================================
# Memory utilities
# ============================================================
def mem_report():
    """Print current memory status"""
    with open('/proc/meminfo') as f:
        for line in f:
            if any(x in line for x in ['MemTotal', 'MemAvailable', 'MemFree', 'Buffers', 'Cached']):
                print(line.strip())

def gc_clean():
    """Force garbage collection and report memory"""
    gc.collect()
    mem_report()

def bytes_to_str(n):
    """Convert bytes to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"

# ============================================================
# Numba JIT templates
# ============================================================
def make_numba_parallel(func_code):
    """
    Create a numba JIT-compiled parallel function from string.
    Usage: fn = make_numba_parallel('''
    def process(i, data):
        return data[i] * 2 + 1
    ''')
    """
    local_ns = {}
    exec(func_code, {}, local_ns)
    fn_name = [k for k in local_ns.keys() if callable(local_ns[k])][0]
    fn = local_ns[fn_name]
    return jit(nopython=True, parallel=True)(fn)

@jit(nopython=True, parallel=True)
def numba_prange_sum(arr):
    """Parallel sum using prange"""
    total = 0.0
    for i in prange(len(arr)):
        total += arr[i]
    return total

@jit(nopython=True)
def numba_mean(data):
    """Fast mean computation via numba"""
    return np.mean(data)

# ============================================================
# Chunk processing helpers
# ============================================================
def chunked_csv_processor(filepath, chunk_size=50_000, processor=None, **kwargs):
    """
    Process large CSV file in chunks using csv module.
    processor: callable that takes list of dicts (rows) and returns result
    
    Usage:
        results = chunked_csv_processor('big.csv', chunk_size=100000,
                                        processor=lambda rows: sum(r['col'] for r in rows))
    """
    results = []
    with open(filepath, 'r', newline='') as f:
        reader = csv.DictReader(f)
        buffer = []
        for row in reader:
            buffer.append(row)
            if len(buffer) >= chunk_size:
                if processor:
                    results.append(processor(buffer))
                buffer = []
                gc.collect()
        if buffer and processor:
            results.append(processor(buffer))
    return results

def chunked_jsonl_processor(filepath, chunk_size=1000, processor=None):
    """
    Process JSONL file in chunks.
    processor: callable that takes dict and returns result
    """
    import json
    results = []
    buffer = []
    with open(filepath, 'r') as f:
        for line in f:
            obj = json.loads(line)
            if processor:
                buffer.append(processor(obj))
            if len(buffer) >= chunk_size:
                results.extend(buffer)
                buffer = []
                gc.collect()
        if buffer:
            results.extend(buffer)
    gc.collect()
    return results

def chunked_npy_processor(npypath, processor, chunk_size=1_000_000, dtype=np.float64, mmap_mode='r'):
    """
    Process .npy file in chunks without loading all into memory.
    processor: callable that takes numpy array chunk
    """
    data = np.load(npypath, mmap_mode=mmap_mode)
    results = []
    for start in range(0, len(data), chunk_size):
        chunk = np.array(data[start:start+chunk_size], dtype=dtype)
        results.append(processor(chunk))
        del chunk
        gc.collect()
    del data
    gc.collect()
    return results

# ============================================================
# Fast string matching (rapidfuzz)
# ============================================================
def fast_match(query, choices, scorer=None, limit=5):
    """
    Fast fuzzy string matching using rapidfuzz.
    scorer options: fuzz.WRatio, fuzz.partial_ratio, fuzz.token_sort_ratio
    """
    from rapidfuzz import fuzz, process
    if scorer is None:
        scorer = fuzz.WRatio
    return process.extract(query, choices, scorer=scorer, limit=limit)

def fast_dedupe(strings, threshold=85):
    """Deduplicate strings using rapidfuzz"""
    from rapidfuzz import fuzz
    seen = []
    for s in strings:
        if not any(fuzz.ratio(s, e) > threshold for e in seen):
            seen.append(s)
    return seen

# ============================================================
# Vectorized numpy operations
# ============================================================
def vectorized_logsumexp(arr):
    """Log-sum-exp trick for numerical stability"""
    max_arr = np.max(arr)
    return max_arr + np.log(np.sum(np.exp(arr - max_arr)))

def vectorized_softmax(arr):
    """Numerically stable softmax"""
    max_arr = np.max(arr)
    exp_arr = np.exp(arr - max_arr)
    return exp_arr / np.sum(exp_arr)

def vectorized_sigmoid(arr):
    """Vectorized sigmoid"""
    return 1.0 / (1.0 + np.exp(-arr))

# ============================================================
# Memory-mapped array helpers
# ============================================================
def mmap_array(path, dtype=np.float64, mode='r'):
    """Memory-map large array for efficient access"""
    return np.load(path, mmap_mode=mode)

# ============================================================
# CSV helpers (replacing pandas DataFrame operations)
# ============================================================
def convert_rows_to_numeric(rows, cols=None, dtype=np.float32):
    """
    Convert specific columns to numeric values.
    rows: list of dicts
    cols: list of column names to convert (None = all numeric cols)
    Returns list of lists with numeric values converted.
    """
    if not rows:
        return []
    
    # Auto-detect numeric columns if not specified
    if cols is None:
        cols = [k for k in rows[0].keys() if k.replace('.', '').replace('-', '').isdigit()]
    
    result = []
    for row in rows:
        new_row = {}
        for k, v in row.items():
            if k in cols:
                try:
                    new_row[k] = dtype.type(v)
                except (ValueError, TypeError):
                    new_row[k] = v
            else:
                new_row[k] = v
        result.append(new_row)
    return result

def split_rows(rows, n_chunks):
    """Split list of rows into n roughly equal chunks"""
    if not rows:
        return []
    chunk_size = len(rows) // n_chunks
    result = []
    for i in range(n_chunks):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < n_chunks - 1 else len(rows)
        result.append(rows[start:end])
    return result

# ============================================================
# Progress tracking
# ============================================================
class Progress:
    def __init__(self, total, name=''):
        self.total = total
        self.name = name
        self.current = 0
        self.pct = 0
    
    def update(self, n=1):
        self.current += n
        new_pct = int(100 * self.current / self.total)
        if new_pct != self.pct and new_pct % 10 == 0:
            print(f'{self.name}: {new_pct}% ({self.current}/{self.total})')
            self.pct = new_pct

if __name__ == '__main__':
    print('ILMA Super Coding Helpers loaded!')
    print(f'NumPy: {np.__version__}')
    print(f'Numba JIT: ready')
    print('pandas: removed (using csv module instead)')
    mem_report()