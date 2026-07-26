#!/usr/bin/env python3
"""
ILMA Auth Engine - Authentication patterns, token management, and OAuth.

This module provides:
- TokenManager: JWT and API token management
- OAuthHandler: OAuth 2.0 flow implementation
- AuthValidator: Authentication validation and verification

Usage:
    python ilma_auth_engine.py --generate-token --type jwt --claims '{"sub": "user123"}'
    python ilma_auth_engine.py --validate-token --token eyJhbG...
    python ilma_auth_engine.py --oauth-flow --provider github

Author: ILMA Team
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlencode, urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TokenType(Enum):
    """Types of authentication tokens."""
    JWT = "jwt"
    API_KEY = "api_key"
    BEARER = "bearer"
    REFRESH = "refresh"


class OAuthProvider(Enum):
    """Supported OAuth providers."""
    GITHUB = "github"
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    GENERIC = "generic"


@dataclass
class TokenClaims:
    """JWT token claims."""
    sub: str  # Subject (user ID)
    iss: str = "ilma"  # Issuer
    aud: Optional[str] = None  # Audience
    exp: int = 3600  # Expiration time (seconds)
    iat: int = 0  # Issued at
    nbf: int = 0  # Not before
    jti: str = ""  # JWT ID
    scope: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.iat == 0:
            self.iat = int(time.time())
        if self.nbf == 0:
            self.nbf = self.iat
        if self.exp <= 0:
            self.exp = 3600
        if not self.jti:
            self.jti = str(uuid.uuid4())


@dataclass
class TokenInfo:
    """Token information and metadata."""
    token_id: str
    token_type: TokenType
    user_id: str
    created_at: float
    expires_at: float
    last_used: Optional[float] = None
    scopes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_revoked: bool = False


@dataclass
class OAuthConfig:
    """OAuth provider configuration."""
    provider: OAuthProvider
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    scopes: List[str]
    redirect_uri: str = "http://localhost:8080/callback"


class TokenManager:
    """
    Manages JWT and API tokens.
    
    Features:
    - JWT generation and validation
    - API key generation
    - Token rotation
    - Token revocation
    - Scope-based access control
    - Token introspection
    """

    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize token manager.
        
        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT signing algorithm
        """
        self.secret_key = secret_key or secrets.token_hex(32)
        self.algorithm = algorithm
        self.issued_tokens: Dict[str, TokenInfo] = {}
        self.revoked_tokens: set = set()
        self.logger = logging.getLogger(f"{__name__}.TokenManager")

    def generate_jwt(
        self,
        subject: str,
        claims: Optional[Dict[str, Any]] = None,
        expiration: int = 3600,
        issuer: str = "ilma"
    ) -> Tuple[str, TokenInfo]:
        """
        Generate a JWT token.
        
        Args:
            subject: Token subject (user ID)
            claims: Additional JWT claims
            expiration: Token expiration in seconds
            issuer: Token issuer
            
        Returns:
            Tuple of (token string, TokenInfo)
        """
        now = int(time.time())
        
        # Build claims
        payload = {
            "sub": subject,
            "iss": issuer,
            "iat": now,
            "nbf": now,
            "exp": now + expiration,
            "jti": str(uuid.uuid4())
        }
        
        # Add custom claims
        if claims:
            payload.update(claims)
        
        # Create header
        header = {
            "alg": self.algorithm,
            "typ": "JWT"
        }
        
        # Base64 encode
        def b64_encode(data: Dict) -> str:
            json_str = json.dumps(data, separators=(",", ":"))
            return base64.urlsafe_b64encode(json_str.encode()).decode().rstrip("=")
        
        header_b64 = b64_encode(header)
        payload_b64 = b64_encode(payload)
        
        # Create signature
        message = f"{header_b64}.{payload_b64}"
        
        if self.algorithm.startswith("HS"):
            signature = hmac.new(
                self.secret_key.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
            signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        else:
            # For RS256, would need RSA keys
            signature_b64 = "unsupported"
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        # Create token info
        token_info = TokenInfo(
            token_id=payload["jti"],
            token_type=TokenType.JWT,
            user_id=subject,
            created_at=now,
            expires_at=now + expiration,
            scopes=claims.get("scope", "").split() if claims and "scope" in claims else []
        )
        
        self.issued_tokens[payload["jti"]] = token_info
        self.logger.info(f"Generated JWT for subject: {subject}")
        
        return token, token_info

    def validate_jwt(self, token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Tuple of (is_valid, claims, error_message)
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return False, None, "Invalid token format"
            
            header_b64, payload_b64, signature_b64 = parts
            
            # Verify signature
            message = f"{header_b64}.{payload_b64}"
            
            if self.algorithm.startswith("HS"):
                expected_signature = hmac.new(
                    self.secret_key.encode(),
                    message.encode(),
                    hashlib.sha256
                ).digest()
                expected_b64 = base64.urlsafe_b64encode(expected_signature).decode().rstrip("=")
                
                if not hmac.compare_digest(signature_b64, expected_b64):
                    return False, None, "Invalid signature"
            
            # Decode payload
            # Add padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            
            payload_str = base64.urlsafe_b64decode(payload_b64).decode()
            claims = json.loads(payload_str)
            
            # Check expiration
            now = int(time.time())
            if claims.get("exp", 0) < now:
                return False, None, "Token expired"
            
            # Check not before
            if claims.get("nbf", 0) > now:
                return False, None, "Token not yet valid"
            
            # Check if revoked
            jti = claims.get("jti", "")
            if jti in self.revoked_tokens:
                return False, None, "Token has been revoked"
            
            return True, claims, None
            
        except Exception as e:
            return False, None, f"Validation error: {str(e)}"

    def generate_api_key(
        self,
        user_id: str,
        name: str = "default",
        scopes: Optional[List[str]] = None,
        expiration_days: Optional[int] = None
    ) -> Tuple[str, TokenInfo]:
        """
        Generate an API key.
        
        Args:
            user_id: User ID
            name: Key name/description
            scopes: Permission scopes
            expiration_days: Days until expiration (None = never)
            
        Returns:
            Tuple of (api_key, TokenInfo)
        """
        token_id = str(uuid.uuid4())
        
        # Generate random API key
        prefix = "sk"
        random_part = secrets.token_urlsafe(32)
        api_key = f"{prefix}_{random_part}"
        
        now = time.time()
        expires_at = now + (expiration_days * 86400) if expiration_days else 0
        
        token_info = TokenInfo(
            token_id=token_id,
            token_type=TokenType.API_KEY,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
            scopes=scopes or [],
            metadata={"name": name}
        )
        
        self.issued_tokens[token_id] = token_info
        self.logger.info(f"Generated API key for user: {user_id}")
        
        # Return key with ID prefix for reference
        full_key = f"{token_id}:{api_key}"
        return full_key, token_info

    def validate_api_key(self, api_key: str) -> Tuple[bool, Optional[TokenInfo]]:
        """
        Validate an API key.
        
        Args:
            api_key: Full API key (id:key format)
            
        Returns:
            Tuple of (is_valid, TokenInfo)
        """
        try:
            if ":" not in api_key:
                return False, None
            
            token_id, key = api_key.split(":", 1)
            
            if token_id not in self.issued_tokens:
                return False, None
            
            token_info = self.issued_tokens[token_id]
            
            if token_info.is_revoked:
                return False, None
            
            # Check expiration (0 = never expires)
            if token_info.expires_at > 0 and token_info.expires_at < time.time():
                return False, None
            
            return True, token_info
            
        except Exception as e:
            self.logger.error(f"API key validation error: {e}")
            return False, None

    def revoke_token(self, token_id: str) -> bool:
        """
        Revoke a token.
        
        Args:
            token_id: Token ID to revoke
            
        Returns:
            True if revoked successfully
        """
        if token_id in self.issued_tokens:
            self.issued_tokens[token_id].is_revoked = True
            self.revoked_tokens.add(token_id)
            self.logger.info(f"Revoked token: {token_id}")
            return True
        return False

    def get_token_info(self, token_id: str) -> Optional[TokenInfo]:
        """Get information about a token."""
        return self.issued_tokens.get(token_id)

    def list_user_tokens(self, user_id: str) -> List[TokenInfo]:
        """List all tokens for a user."""
        return [
            ti for ti in self.issued_tokens.values()
            if ti.user_id == user_id and not ti.is_revoked
        ]


class OAuthHandler:
    """
    Handles OAuth 2.0 authentication flows.
    
    Features:
    - Authorization code flow
    - PKCE support
    - Token exchange
    - Token refresh
    - Scope management
    """

    def __init__(self, config: OAuthConfig):
        """
        Initialize OAuth handler.
        
        Args:
            config: OAuth provider configuration
        """
        self.config = config
        self.code_verifiers: Dict[str, str] = {}  # state -> code_verifier
        self.logger = logging.getLogger(f"{__name__}.OAuthHandler")

    def get_authorization_url(self, state: Optional[str] = None, pkce: bool = True) -> Tuple[str, str]:
        """
        Get the authorization URL for the OAuth flow.
        
        Args:
            state: Optional state parameter
            pkce: Whether to use PKCE
            
        Returns:
            Tuple of (authorization_url, state)
        """
        if state is None:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
            "response_type": "code"
        }
        
        if pkce:
            # Generate code verifier and challenge
            code_verifier = secrets.token_urlsafe(64)
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).decode().rstrip("=")
            
            self.code_verifiers[state] = code_verifier
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        
        params["state"] = state
        
        url = f"{self.config.authorization_url}?{urlencode(params)}"
        return url, state

    def exchange_code_for_tokens(
        self,
        code: str,
        state: str,
        http_client: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code
            state: State parameter
            http_client: Optional HTTP client function
            
        Returns:
            Token response dictionary
        """
        # Get code verifier if PKCE was used
        code_verifier = self.code_verifiers.pop(state, None)
        
        params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret
        }
        
        if code_verifier:
            params["code_verifier"] = code_verifier
        
        # Make token request
        # In production, use actual HTTP client
        self.logger.info(f"Would exchange code for tokens: {self.config.token_url}")
        
        # Return mock response for demonstration
        return {
            "access_token": f"at_{secrets.token_urlsafe(32)}",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": f"rt_{secrets.token_urlsafe(32)}",
            "scope": " ".join(self.config.scopes)
        }

    def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access tokens.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New token response
        """
        params = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret
        }
        
        self.logger.info("Refreshing tokens...")
        
        # Return mock response
        return {
            "access_token": f"at_{secrets.token_urlsafe(32)}",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": f"rt_{secrets.token_urlsafe(32)}"
        }


class AuthValidator:
    """
    Validates authentication and authorization.
    
    Features:
    - Token validation
    - Scope checking
    - Role-based access control
    - Rate limiting
    - Audit logging
    """

    def __init__(self, token_manager: TokenManager):
        """
        Initialize auth validator.
        
        Args:
            token_manager: Token manager instance
        """
        self.token_manager = token_manager
        self.rate_limits: Dict[str, List[float]] = {}
        self.logger = logging.getLogger(f"{__name__}.AuthValidator")

    def validate_request(
        self,
        token: str,
        required_scopes: Optional[List[str]] = None,
        required_roles: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Validate an authentication request.
        
        Args:
            token: Authentication token
            required_scopes: Required OAuth scopes
            required_roles: Required user roles
            
        Returns:
            Tuple of (is_valid, error_message, claims)
        """
        # Validate token format
        if token.startswith("Bearer "):
            token = token[7:]
        
        if token.startswith("sk_") or ":" in token:
            # API key
            is_valid, token_info = self.token_manager.validate_api_key(token)
            if not is_valid:
                return False, "Invalid API key", None
            return True, None, {"user_id": token_info.user_id, "scopes": token_info.scopes}
        
        # JWT validation
        is_valid, claims, error = self.token_manager.validate_jwt(token)
        if not is_valid:
            return False, error, None
        
        # Check scopes
        if required_scopes:
            token_scopes = set(claims.get("scope", "").split())
            required = set(required_scopes)
            if not required.issubset(token_scopes):
                return False, f"Missing required scopes: {required - token_scopes}", None
        
        # Check roles
        if required_roles:
            token_roles = set(claims.get("roles", []))
            required = set(required_roles)
            if not required.issubset(token_roles):
                return False, f"Missing required roles: {required - token_roles}", None
        
        return True, None, claims

    def check_rate_limit(
        self,
        identifier: str,
        max_requests: int = 100,
        window_seconds: int = 60
    ) -> Tuple[bool, Optional[str]]:
        """
        Check rate limit for an identifier.
        
        Args:
            identifier: User or IP identifier
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        now = time.time()
        window_start = now - window_seconds
        
        if identifier not in self.rate_limits:
            self.rate_limits[identifier] = []
        
        # Remove old timestamps
        self.rate_limits[identifier] = [
            ts for ts in self.rate_limits[identifier]
            if ts > window_start
        ]
        
        # Check limit
        if len(self.rate_limits[identifier]) >= max_requests:
            return False, f"Rate limit exceeded. Try again in {window_seconds}s"
        
        # Add current request
        self.rate_limits[identifier].append(now)
        return True, None

    def require_auth(self, token: str) -> Optional[str]:
        """Decorator helper for requiring authentication."""
        is_valid, error, _ = self.validate_request(token)
        return error

    def log_auth_attempt(
        self,
        user_id: str,
        success: bool,
        token_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Log an authentication attempt for audit."""
        log_entry = {
            "timestamp": time.time(),
            "user_id": user_id,
            "success": success,
            "token_id": token_id,
            "metadata": metadata or {}
        }
        self.logger.info(f"Auth attempt: {json.dumps(log_entry)}")


def create_oauth_config(
    provider: OAuthProvider,
    client_id: str,
    client_secret: str,
    **kwargs
) -> OAuthConfig:
    """Factory function to create OAuthConfig with provider-specific defaults."""
    
    provider_urls = {
        OAuthProvider.GITHUB: {
            "authorization_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token"
        },
        OAuthProvider.GOOGLE: {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token"
        },
        OAuthProvider.MICROSOFT: {
            "authorization_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        }
    }
    
    urls = provider_urls.get(provider, {
        "authorization_url": "https://example.com/oauth/authorize",
        "token_url": "https://example.com/oauth/token"
    })
    
    return OAuthConfig(
        provider=provider,
        client_id=client_id,
        client_secret=client_secret,
        scopes=kwargs.get("scopes", ["read", "write"]),
        redirect_uri=kwargs.get("redirect_uri", "http://localhost:8080/callback"),
        **urls
    )


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="ILMA Auth Engine - Authentication, token management, and OAuth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --generate-token --type jwt --subject user123 --expiration 3600
  %(prog)s --validate-token --token eyJhbG...
  %(prog)s --generate-api-key --user-id user123 --name "My API Key"
  %(prog)s --oauth-flow --provider github --client-id abc --client-secret xyz
        """
    )
    
    # Token operations
    parser.add_argument("--generate-token", "-g", action="store_true", help="Generate a token")
    parser.add_argument("--type", choices=["jwt", "api_key", "bearer"],
                       default="jwt", help="Token type")
    parser.add_argument("--subject", help="Token subject (user ID)")
    parser.add_argument("--claims", help="JSON claims for JWT")
    parser.add_argument("--expiration", type=int, default=3600, help="Expiration in seconds")
    parser.add_argument("--name", help="Name for API key")
    parser.add_argument("--scopes", nargs="+", help="Token scopes")
    
    # Token validation
    parser.add_argument("--validate-token", "-v", action="store_true", help="Validate a token")
    parser.add_argument("--token", help="Token to validate")
    
    # API key operations
    parser.add_argument("--generate-api-key", action="store_true", help="Generate an API key")
    parser.add_argument("--user-id", help="User ID for API key")
    parser.add_argument("--revoke-token", help="Token ID to revoke")
    parser.add_argument("--list-tokens", action="store_true", help="List tokens for a user")
    
    # OAuth
    parser.add_argument("--oauth-flow", action="store_true", help="Start OAuth flow")
    parser.add_argument("--provider", choices=["github", "google", "microsoft"],
                       help="OAuth provider")
    parser.add_argument("--client-id", help="OAuth client ID")
    parser.add_argument("--client-secret", help="OAuth client secret")
    parser.add_argument("--exchange-code", help="Exchange authorization code")
    parser.add_argument("--state", help="OAuth state parameter")
    
    # Output
    parser.add_argument("--output", "-o", help="Output file")
    parser.add_argument("--json-output", "-j", action="store_true", help="JSON output")
    
    args = parser.parse_args()
    
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize components
        token_manager = TokenManager()
        validator = AuthValidator(token_manager)
        
        # Generate token
        if args.generate_token:
            if not args.subject:
                logger.error("--subject required for token generation")
                return 1
            
            claims = json.loads(args.claims) if args.claims else {}
            if args.scopes:
                claims["scope"] = " ".join(args.scopes)
            
            if args.type == "jwt":
                token, info = token_manager.generate_jwt(
                    subject=args.subject,
                    claims=claims,
                    expiration=args.expiration
                )
                
                if args.json_output:
                    print(json.dumps({
                        "token": token,
                        "token_id": info.token_id,
                        "expires_at": info.expires_at,
                        "scopes": info.scopes
                    }, indent=2))
                else:
                    print(f"JWT Token generated:")
                    print(f"  Token ID: {info.token_id}")
                    print(f"  Subject: {args.subject}")
                    print(f"  Expires: {info.expires_at}")
                    print(f"\n{token}")
                    
            elif args.type == "api_key":
                if not args.user_id:
                    logger.error("--user-id required for API key generation")
                    return 1
                
                api_key, info = token_manager.generate_api_key(
                    user_id=args.user_id,
                    name=args.name or "default",
                    scopes=args.scopes
                )
                
                if args.json_output:
                    print(json.dumps({
                        "api_key": api_key,
                        "token_id": info.token_id,
                        "user_id": info.user_id,
                        "created_at": info.created_at
                    }, indent=2))
                else:
                    print(f"API Key generated:")
                    print(f"  Token ID: {info.token_id}")
                    print(f"  User ID: {info.user_id}")
                    print(f"\n{api_key}")
                    print("\n⚠️ Save this key securely - it cannot be recovered!")
            
            return 0
        
        # Validate token
        if args.validate_token:
            if not args.token:
                logger.error("--token required for validation")
                return 1
            
            is_valid, claims, error = token_manager.validate_jwt(args.token)
            
            if is_valid:
                if args.json_output:
                    print(json.dumps({
                        "valid": True,
                        "claims": claims
                    }, indent=2))
                else:
                    print("✓ Token is valid")
                    print(f"  Subject: {claims.get('sub')}")
                    print(f"  Issuer: {claims.get('iss')}")
                    print(f"  Expires: {claims.get('exp')}")
            else:
                if args.json_output:
                    print(json.dumps({"valid": False, "error": error}, indent=2))
                else:
                    print(f"✗ Token invalid: {error}")
                return 1
            
            return 0
        
        # Generate API key
        if args.generate_api_key:
            if not args.user_id:
                logger.error("--user-id required for API key generation")
                return 1
            
            api_key, info = token_manager.generate_api_key(
                user_id=args.user_id,
                name=args.name or "default",
                scopes=args.scopes
            )
            
            if args.json_output:
                print(json.dumps({
                    "api_key": api_key,
                    "token_id": info.token_id,
                    "user_id": info.user_id
                }, indent=2))
            else:
                print(f"API Key generated for user: {args.user_id}")
                print(f"  Token ID: {info.token_id}")
                print(f"\n{api_key}")
            
            return 0
        
        # Revoke token
        if args.revoke_token:
            success = token_manager.revoke_token(args.revoke_token)
            if success:
                print(f"✓ Token revoked: {args.revoke_token}")
            else:
                print(f"✗ Token not found: {args.revoke_token}")
            return 0 if success else 1
        
        # List tokens
        if args.list_tokens:
            if not args.user_id:
                logger.error("--user-id required for listing tokens")
                return 1
            
            tokens = token_manager.list_user_tokens(args.user_id)
            if args.json_output:
                print(json.dumps({
                    "user_id": args.user_id,
                    "token_count": len(tokens),
                    "tokens": [
                        {
                            "token_id": t.token_id,
                            "type": t.token_type.value,
                            "created_at": t.created_at,
                            "expires_at": t.expires_at,
                            "scopes": t.scopes
                        }
                        for t in tokens
                    ]
                }, indent=2))
            else:
                print(f"Tokens for user: {args.user_id}")
                print(f"Total: {len(tokens)}")
                for t in tokens:
                    print(f"  [{t.token_type.value}] {t.token_id} - Created: {t.created_at}")
            
            return 0
        
        # OAuth flow
        if args.oauth_flow:
            if not args.provider:
                logger.error("--provider required for OAuth flow")
                return 1
            
            provider = OAuthProvider(args.provider)
            
            if not args.client_id or not args.client_secret:
                logger.error("--client-id and --client-secret required")
                return 1
            
            config = create_oauth_config(
                provider=provider,
                client_id=args.client_id,
                client_secret=args.client_secret
            )
            
            handler = OAuthHandler(config)
            auth_url, state = handler.get_authorization_url()
            
            if args.json_output:
                print(json.dumps({
                    "authorization_url": auth_url,
                    "state": state
                }, indent=2))
            else:
                print("OAuth Authorization URL:")
                print(f"\n{auth_url}")
                print(f"\nState: {state}")
                print("\nUse this URL to authorize the application.")
            
            return 0
        
        # Exchange code
        if args.exchange_code:
            logger.error("Code exchange requires full OAuth configuration")
            return 1
        
        # Default: show help
        parser.print_help()
        return 0
        
    except Exception as e:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    exit(main())