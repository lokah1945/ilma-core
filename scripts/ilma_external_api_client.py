#!/usr/bin/env python3
"""
ILMA External API Client v1.0
=============================
Robust API client with rate limiting, retries, and response parsing.
Supports multiple API providers with configurable rate limits.

Classes:
- RateLimiter: Token bucket rate limiting
- RetryHandler: Exponential backoff retry logic
- ResponseParser: Normalize API responses

Usage:
    python3 ilma_external_api_client.py call --url https://api.example.com/data
    python3 ilma_external_api_client.py batch --file requests.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

WORKSPACE = Path("/root/.hermes/profiles/ilma")
CACHE_DIR = WORKSPACE / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RATE_LIMIT = 100  # requests per minute


class HttpMethod(str, Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies."""
    FIXED = "fixed"
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"


@dataclass
class APIResponse:
    """Normalized API response."""
    status_code: int
    headers: Dict[str, str]
    body: Any
    elapsed_ms: float
    cached: bool = False
    error: Optional[str] = None


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a provider."""
    requests_per_minute: int = DEFAULT_RATE_LIMIT
    burst_size: int = 10
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET


@dataclass
class APIError(Exception):
    """API client error."""
    message: str
    status_code: Optional[int] = None
    retry_after: Optional[int] = None
    is_rate_limit: bool = False

    def __str__(self) -> str:
        base = self.message
        if self.status_code:
            base += f" (HTTP {self.status_code})"
        if self.retry_after:
            base += f" (retry after {self.retry_after}s)"
        return base


# ============================================================================
# RateLimiter
# ============================================================================

class RateLimiter:
    """
    Token bucket rate limiter for API requests.
    Supports configurable rate limits and burst sizes.

    Example:
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        await limiter.acquire("api_provider")
        # Make request
    """

    def __init__(self, requests_per_minute: int = DEFAULT_RATE_LIMIT, burst_size: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.tokens: Dict[str, float] = {}
        self.last_refill: Dict[str, datetime] = {}
        self.wait_times: Dict[str, List[float]] = {}
        logger.info(f"RateLimiter initialized: {requests_per_minute} req/min, burst={burst_size}")

    def _get_bucket_key(self, provider: str) -> str:
        """Get bucket key for provider."""
        return f"bucket:{provider}"

    async def acquire(self, provider: str = "default", tokens: int = 1) -> float:
        """
        Acquire tokens for a provider.
        Returns wait time in seconds before tokens are available.
        """
        key = self._get_bucket_key(provider)
        now = datetime.now()

        if key not in self.tokens:
            self.tokens[key] = float(self.burst_size)
            self.last_refill[key] = now

        last_refill = self.last_refill.get(key, now)
        elapsed = (now - last_refill).total_seconds()

        refill_rate = self.requests_per_minute / 60.0
        new_tokens = elapsed * refill_rate

        self.tokens[key] = min(self.burst_size, self.tokens[key] + new_tokens)
        self.last_refill[key] = now

        if self.tokens[key] >= tokens:
            self.tokens[key] -= tokens
            return 0.0

        tokens_needed = tokens - self.tokens[key]
        wait_time = tokens_needed / refill_rate

        if provider not in self.wait_times:
            self.wait_times[provider] = []
        self.wait_times[provider].append(wait_time)
        if len(self.wait_times[provider]) > 100:
            self.wait_times[provider] = self.wait_times[provider][-100:]

        await asyncio.sleep(wait_time)
        self.tokens[key] = 0
        return wait_time

    def get_wait_stats(self, provider: str) -> Dict[str, float]:
        """Get wait time statistics for provider."""
        times = self.wait_times.get(provider, [])
        if not times:
            return {"avg": 0.0, "max": 0.0, "count": 0}

        return {
            "avg": sum(times) / len(times),
            "max": max(times),
            "count": len(times)
        }

    def reset(self, provider: Optional[str] = None) -> None:
        """Reset rate limiter state."""
        if provider:
            key = self._get_bucket_key(provider)
            self.tokens.pop(key, None)
            self.last_refill.pop(key, None)
        else:
            self.tokens.clear()
            self.last_refill.clear()
        logger.debug(f"Rate limiter reset for: {provider or 'all'}")


# ============================================================================
# RetryHandler
# ============================================================================

class RetryHandler:
    """
    Exponential backoff retry handler with jitter.
    Handles transient failures and rate limits.

    Example:
        handler = RetryHandler(max_retries=3, base_delay=1.0)
        result = await handler.execute(api_call_func)
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_stats: Dict[str, int] = {}
        logger.info(f"RetryHandler initialized: max_retries={max_retries}, base_delay={base_delay}s")

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter."""
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)

        if self.jitter:
            import random
            delay *= (0.5 + random.random())

        return delay

    async def execute(
        self,
        func: Callable,
        *args,
        retry_on: Tuple[type, ...] = (Exception,),
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic.
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"Request succeeded after {attempt} retries")
                return result

            except Exception as e:
                last_exception = e
                should_retry = isinstance(e, retry_on)

                if not should_retry or attempt >= self.max_retries:
                    logger.error(f"Request failed permanently: {e}")
                    raise

                delay = self._calculate_delay(attempt)
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}), "
                              f"retrying in {delay:.2f}s: {e}")

                await asyncio.sleep(delay)

        raise last_exception

    def get_stats(self) -> Dict[str, int]:
        """Get retry statistics."""
        return self.retry_stats.copy()


# ============================================================================
# ResponseParser
# ============================================================================

class ResponseParser:
    """
    Normalize and parse API responses.
    Handles JSON, pagination, and error responses.

    Example:
        parser = ResponseParser()
        data = parser.parse(response, schema={"items": list, "total": int})
    """

    def __init__(self):
        self.parse_stats = {"success": 0, "error": 0, "cached": 0}
        logger.info("ResponseParser initialized")

    def parse(
        self,
        response: APIResponse,
        expected_fields: Optional[List[str]] = None,
        strict: bool = False
    ) -> Dict[str, Any]:
        """Parse API response and validate fields."""
        if response.error:
            self.parse_stats["error"] += 1
            raise APIError(f"Response contains error: {response.error}")

        if response.status_code >= 400:
            self.parse_stats["error"] += 1
            raise APIError(
                f"HTTP error: {response.status_code}",
                status_code=response.status_code
            )

        result = self._extract_body(response.body)

        if expected_fields and strict:
            self._validate_fields(result, expected_fields)

        self.parse_stats["success"] += 1
        return result

    def _extract_body(self, body: Any) -> Dict[str, Any]:
        """Extract body from response, handling various formats."""
        if isinstance(body, dict):
            return body

        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"raw": body}

        if hasattr(body, "data"):
            return body.data if isinstance(body.data, dict) else {"data": body.data}

        return {"raw": str(body)}

    def _validate_fields(self, data: Dict[str, Any], fields: List[str]) -> None:
        """Validate that expected fields are present."""
        missing = [f for f in fields if f not in data]
        if missing:
            raise APIError(f"Missing expected fields: {missing}")

    def parse_list(
        self,
        response: APIResponse,
        item_path: str = "items"
    ) -> List[Dict[str, Any]]:
        """Parse response containing a list of items."""
        data = self.parse(response)

        if item_path in data:
            items = data[item_path]
        else:
            items = data if isinstance(data, list) else [data]

        return items

    def parse_paginated(
        self,
        response: APIResponse
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Parse paginated response and extract next cursor/page."""
        data = self.parse(response)

        items = data.get("items", data.get("data", []))
        if not isinstance(items, list):
            items = [items]

        next_cursor = data.get("next_cursor", data.get("next_page", None))

        return items, next_cursor

    def extract_value(
        self,
        response: APIResponse,
        path: str
    ) -> Any:
        """Extract value from response using dot notation path."""
        data = self.parse(response)

        for key in path.split("."):
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None

        return data

    def get_stats(self) -> Dict[str, int]:
        """Get parsing statistics."""
        return self.parse_stats.copy()


# ============================================================================
# ExternalAPIClient
# ============================================================================

class ExternalAPIClient:
    """
    Full-featured API client with rate limiting, retries, and parsing.
    Supports caching and multiple providers.

    Example:
        client = ExternalAPIClient()
        result = await client.get("https://api.example.com/data")
        results = await client.batch_get(["https://api.example.com/1", "https://api.example.com/2"])
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        retry_handler: Optional[RetryHandler] = None,
        cache_dir: Optional[Path] = None
    ):
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_handler = retry_handler or RetryHandler()
        self.parser = ResponseParser()
        self.cache_dir = cache_dir or CACHE_DIR / "api_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.providers: Dict[str, RateLimitConfig] = {}
        logger.info("ExternalAPIClient initialized")

    def configure_provider(
        self,
        provider: str,
        requests_per_minute: int,
        burst_size: int = 10
    ) -> None:
        """Configure rate limit for a provider."""
        self.providers[provider] = RateLimitConfig(
            requests_per_minute=requests_per_minute,
            burst_size=burst_size
        )
        logger.info(f"Provider {provider} configured: {requests_per_minute} req/min")

    async def _get_cache(self, cache_key: str) -> Optional[APIResponse]:
        """Get cached response."""
        cache_file = self.cache_dir / f"{hashlib.md5(cache_key.encode()).hexdigest()}.json"

        if cache_file.exists():
            age = (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).total_seconds()
            if age < 300:  # 5 minute cache
                try:
                    with open(cache_file) as f:
                        data = json.load(f)
                    return APIResponse(
                        status_code=data["status_code"],
                        headers=data["headers"],
                        body=data["body"],
                        elapsed_ms=data["elapsed_ms"],
                        cached=True
                    )
                except Exception as e:
                    logger.warning(f"Cache read failed: {e}")
        return None

    async def _set_cache(self, cache_key: str, response: APIResponse) -> None:
        """Cache response."""
        cache_file = self.cache_dir / f"{hashlib.md5(cache_key.encode()).hexdigest()}.json"

        try:
            with open(cache_file, "w") as f:
                json.dump({
                    "status_code": response.status_code,
                    "headers": response.headers,
                    "body": response.body,
                    "elapsed_ms": response.elapsed_ms,
                    "cached_at": datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    async def request(
        self,
        method: HttpMethod,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        provider: str = "default",
        use_cache: bool = False,
        timeout: int = DEFAULT_TIMEOUT
    ) -> APIResponse:
        """Make HTTP request with rate limiting and retries."""
        import urllib.request
        import urllib.parse

        cache_key = f"{method.value}:{url}:{json.dumps(params or {})}"

        if use_cache:
            cached = await self._get_cache(cache_key)
            if cached:
                logger.debug(f"Cache hit: {url}")
                self.parser.parse_stats["cached"] += 1
                return cached

        await self.rate_limiter.acquire(provider)

        start_time = time.time()

        def make_request() -> APIResponse:
            nonlocal start_time

            try:
                import urllib.error

                req_headers = headers or {}
                req_headers.setdefault("User-Agent", "ILMA-API-Client/1.0")

                encoded_body = None
                if body:
                    if isinstance(body, dict):
                        encoded_body = json.dumps(body).encode()
                        req_headers.setdefault("Content-Type", "application/json")
                    else:
                        encoded_body = body

                url_with_params = url
                if params:
                    url_with_params = f"{url}?{urllib.parse.urlencode(params)}"

                request_obj = urllib.request.Request(
                    url_with_params,
                    data=encoded_body,
                    headers=req_headers,
                    method=method.value
                )

                with urllib.request.urlopen(request_obj, timeout=timeout) as response:
                    response_body = response.read()
                    try:
                        body_json = json.loads(response_body)
                    except json.JSONDecodeError:
                        body_json = response_body.decode()

                    elapsed_ms = (time.time() - start_time) * 1000

                    return APIResponse(
                        status_code=response.status,
                        headers=dict(response.headers),
                        body=body_json,
                        elapsed_ms=elapsed_ms
                    )

            except urllib.error.HTTPError as e:
                elapsed_ms = (time.time() - start_time) * 1000
                error_body = e.read().decode() if e.fp else ""
                try:
                    error_json = json.loads(error_body)
                except ValueError:
                    error_json = error_body

                is_rate_limit = e.code == 429
                retry_after = None
                if is_rate_limit and "Retry-After" in e.headers:
                    retry_after = int(e.headers["Retry-After"])

                return APIResponse(
                    status_code=e.code,
                    headers=dict(e.headers),
                    body=error_json,
                    elapsed_ms=elapsed_ms,
                    error=f"HTTP {e.code}" if not is_rate_limit else None
                )

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                return APIResponse(
                    status_code=0,
                    headers={},
                    body=None,
                    elapsed_ms=elapsed_ms,
                    error=str(e)
                )

        try:
            response = make_request()
        except Exception as e:
            # Retry logic with backoff
            for attempt in range(self.retry_handler.max_retries):
                delay = self.retry_handler._calculate_delay(attempt)
                logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {delay:.2f}s: {e}")
                import time as time_module
                time_module.sleep(delay)
                try:
                    response = make_request()
                    break
                except Exception:
                    continue
            else:
                return APIResponse(
                    status_code=0,
                    headers={},
                    body=None,
                    elapsed_ms=(time.time() - start_time) * 1000,
                    error=str(e)
                )

        if response.status_code < 400 and use_cache:
            await self._set_cache(cache_key, response)

        return response

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> APIResponse:
        """GET request."""
        return await self.request(HttpMethod.GET, url, params=params, **kwargs)

    async def post(
        self,
        url: str,
        body: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> APIResponse:
        """POST request."""
        return await self.request(HttpMethod.POST, url, body=body, **kwargs)

    async def batch_get(
        self,
        urls: List[str],
        concurrency: int = 5
    ) -> List[APIResponse]:
        """Make multiple GET requests with limited concurrency."""
        semaphore = asyncio.Semaphore(concurrency)

        async def get_with_semaphore(url: str) -> APIResponse:
            async with semaphore:
                return await self.get(url)

        return await asyncio.gather(*[get_with_semaphore(url) for url in urls])


# ============================================================================
# Main CLI
# ============================================================================

async def async_main(args: argparse.Namespace) -> int:
    """Async main entry point."""
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    client = ExternalAPIClient()

    if args.action == "call":
        if not args.url:
            logger.error("--url required for call action")
            return 1

        headers = {}
        if args.header:
            for h in args.header:
                if ":" in h:
                    k, v = h.split(":", 1)
                    headers[k.strip()] = v.strip()

        body = None
        if args.body:
            try:
                body = json.loads(args.body)
            except json.JSONDecodeError:
                body = {"data": args.body}

        response = await client.request(
            method=HttpMethod(args.method.upper()),
            url=args.url,
            headers=headers,
            body=body,
            use_cache=args.cache
        )

        print(f"Status: {response.status_code}")
        print(f"Elapsed: {response.elapsed_ms:.2f}ms")
        print(f"Cached: {response.cached}")

        if args.output:
            with open(args.output, "w") as f:
                json.dump({
                    "status_code": response.status_code,
                    "body": response.body,
                    "elapsed_ms": response.elapsed_ms,
                    "cached": response.cached
                }, f, indent=2)
            print(f"Response saved to: {args.output}")
        else:
            print(json.dumps(response.body, indent=2) if isinstance(response.body, dict) else response.body)

        return 0 if response.status_code < 400 else 1

    elif args.action == "batch":
        if not args.file:
            logger.error("--file required for batch action")
            return 1

        with open(args.file) as f:
            requests = json.load(f)

        results = []
        for req in requests:
            response = await client.request(
                method=HttpMethod(req.get("method", "GET").upper()),
                url=req["url"],
                body=req.get("body"),
                params=req.get("params")
            )
            results.append({
                "url": req["url"],
                "status": response.status_code,
                "elapsed_ms": response.elapsed_ms
            })

        print(json.dumps(results, indent=2))
        return 0


def main() -> int:
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ILMA External API Client",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "action",
        choices=["call", "batch"],
        help="Action to perform"
    )

    parser.add_argument("--url", help="API URL for call action")
    parser.add_argument("--method", default="GET", choices=["GET", "POST", "PUT", "DELETE"],
                        help="HTTP method")
    parser.add_argument("--body", help="Request body (JSON string)")
    parser.add_argument("--header", action="append", help="Custom header (key:value)")
    parser.add_argument("--cache", action="store_true", help="Enable response caching")
    parser.add_argument("--output", help="Save response to file")

    parser.add_argument("--file", help="JSON file with batch requests for batch action")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent requests")

    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())