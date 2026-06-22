import math
from typing import Any

def is_prime(n: Any) -> bool:
    """Determine whether a given integer is prime.

    A prime number is a natural number greater than 1 that has no positive
    divisors other than 1 and itself.

    Args:
        n: The value to test for primality.  Should be an integer or something
            that can be converted to one.  Floats that represent integers
            (e.g., 17.0) are accepted; non-integral floats raise ValueError.

    Returns:
        True if ``n`` is a prime integer, False otherwise.
        Returns False for all values less than 2 (including 0, 1, and
        negative numbers).

    Raises:
        ValueError: If ``n`` is a non-integral float or a value that cannot
            be converted to an integer.
        TypeError: If ``n`` is of an incompatible type (e.g., complex,
            str that doesn't represent an integer).
    """
    # ── Input validation ──────────────────────────────────────────────
    if isinstance(n, bool):
        # bool is a subclass of int in Python; treat booleans as non-prime
        # because they are effectively 0 or 1.
        return False

    if isinstance(n, float):
        if n.is_integer():
            n = int(n)
        else:
            raise ValueError(
                "is_prime() does not accept non-integral floats: "
                f"got {n!r}"
            )

    if not isinstance(n, int):
        try:
            # Attempt conversion only if it looks reasonable (e.g., str).
            # complex, list, etc. will raise TypeError.
            converted = int(n)
        except (ValueError, TypeError) as exc:
            raise TypeError(
                f"is_prime() argument must be convertible to int, got "
                f"{type(n).__name__}: {n!r}"
            ) from exc
        n = converted

    # ── Fast-path cases ───────────────────────────────────────────────
    if n < 2:
        return False
    if n < 4:  # 2, 3
        return True
    if n % 2 == 0:
        return False
    if n % 3 == 0:
        return False

    # ── Trial division ────────────────────────────────────────────────
    # All primes > 3 are of the form 6k ± 1.
    limit = int(math.isqrt(n))  # floor(sqrt(n)) – works for arbitrarily large ints
    candidate = 5
    while candidate <= limit:
        if n % candidate == 0:
            return False
        if n % (candidate + 2) == 0:
            return False
        candidate += 6

    return True