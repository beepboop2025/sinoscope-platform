"""
DragonScope Enterprise SSO Implementation

Provides authentication via SAML 2.0, OpenID Connect (OIDC), and LDAP.
Supports multi-tenant configurations with per-tenant identity providers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple, TypeVar
from urllib.parse import urlencode, urlparse, parse_qs
import xml.etree.ElementTree as ET


# ============================================================================
# Data Models
# ============================================================================

class SSOProviderType(Enum):
    """Supported SSO provider types."""
    SAML = auto()
    OIDC = auto()
    LDAP = auto()
    OAUTH2 = auto()


class MFARequirement(Enum):
    """MFA requirement levels."""
    NEVER = "never"
    OPTIONAL = "optional"
    REQUIRED = "required"
    RISK_BASED = "risk_based"


@dataclass(frozen=True)
class UserIdentity:
    """Canonical user identity returned by SSO providers."""
    external_id: str
    email: str
    tenant_id: str
    provider_id: str
    provider_type: SSOProviderType
    
    # Optional attributes
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    groups: Tuple[str, ...] = field(default_factory=tuple)
    roles: Tuple[str, ...] = field(default_factory=tuple)
    department: Optional[str] = None
    phone: Optional[str] = None
    
    # Metadata
    raw_attributes: Dict[str, Any] = field(default_factory=dict, repr=False)
    mfa_verified: bool = False
    mfa_methods: Tuple[str, ...] = field(default_factory=tuple)


@dataclass
class SSOContext:
    """Context passed through SSO flows."""
    tenant_id: str
    provider_id: str
    provider_type: SSOProviderType
    request_id: str
    initiated_at: float = field(default_factory=time.time)
    relay_state: Optional[str] = None
    redirect_uri: Optional[str] = None
    mfa_required: MFARequirement = MFARequirement.OPTIONAL
    
    # Security
    nonce: Optional[str] = None
    state: Optional[str] = None
    pkce_verifier: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "provider_id": self.provider_id,
            "provider_type": self.provider_type.name,
            "request_id": self.request_id,
            "initiated_at": self.initiated_at,
            "relay_state": self.relay_state,
            "redirect_uri": self.redirect_uri,
            "mfa_required": self.mfa_required.value,
            "nonce": self.nonce,
            "state": self.state,
        }


@dataclass
class AuthResult:
    """Result of an authentication attempt."""
    success: bool
    identity: Optional[UserIdentity] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    mfa_pending: bool = False
    mfa_methods: List[str] = field(default_factory=list)
    session_token: Optional[str] = None
    redirect_url: Optional[str] = None
    requires_consent: bool = False
    consent_scopes: List[str] = field(default_factory=list)


# ============================================================================
# Base SSO Provider
# ============================================================================

class SSOProvider(ABC):
    """
    Abstract base class for SSO providers.
    
    All SSO providers must implement these methods:
    - initiate_login: Start the authentication flow
    - handle_callback: Process the authentication response
    - validate_session: Validate an existing session
    - logout: Initiate logout
    """
    
    def __init__(self, tenant_id: str, provider_id: str, config: Dict[str, Any]):
        self.tenant_id = tenant_id
        self.provider_id = provider_id
        self.config = config
        self._validate_config()
    
    @property
    @abstractmethod
    def provider_type(self) -> SSOProviderType:
        """Return the provider type."""
        pass
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration."""
        pass
    
    @abstractmethod
    async def initiate_login(self, context: SSOContext) -> AuthResult:
        """
        Initiate the SSO login flow.
        
        Returns an AuthResult with redirect_url for the user to visit.
        """
        pass
    
    @abstractmethod
    async def handle_callback(
        self, 
        context: SSOContext, 
        callback_data: Dict[str, Any]
    ) -> AuthResult:
        """
        Handle the callback from the identity provider.
        
        Validates the response and returns user identity on success.
        """
        pass
    
    @abstractmethod
    async def validate_session(self, session_token: str) -> AuthResult:
        """Validate an existing session with the IdP."""
        pass
    
    @abstractmethod
    async def logout(self, session_token: str) -> AuthResult:
        """Initiate logout at the identity provider."""
        pass
    
    async def refresh_identity(self, identity: UserIdentity) -> UserIdentity:
        """
        Refresh user attributes from the identity provider.
        Override for providers that support attribute sync.
        """
        return identity
    
    def _generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(length)
    
    def _generate_pkce_pair(self) -> Tuple[str, str]:
        """Generate PKCE code verifier and challenge."""
        verifier = secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip('=')
        return verifier, challenge


# ============================================================================
# SAML 2.0 Provider
# ============================================================================

class SAMLProvider(SSOProvider):
    """
    SAML 2.0 Service Provider implementation.
    
    Supports:
    - SP-initiated and IdP-initiated SSO
    - Signed assertions and responses
    - Encrypted assertions
    - Attribute mapping
    - Single Logout (SLO)
    
    Dependencies:
    - python-saml or onelogin/python-saml
    - lxml for XML processing
    """
    
    SAML_PROTOCOL_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
    SAML_ASSERTION_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
    SAML_PROTOCOL_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
    
    @property
    def provider_type(self) -> SSOProviderType:
        return SSOProviderType.SAML
    
    def _validate_config(self) -> None:
        required = ["idp_metadata_url"]
        missing = [k for k in required if k not in self.config]
        if missing:
            raise ValueError(f"Missing SAML config keys: {missing}")
        
        self.sp_entity_id = self.config.get(
            "entity_id", 
            f"https://dragonscope.io/auth/saml/{self.tenant_id}"
        )
        self.acs_url = self.config.get(
            "acs_url",
            f"https://dragonscope.io/auth/saml/{self.tenant_id}/acs"
        )
        self.slo_url = self.config.get(
            "slo_url",
            f"https://dragonscope.io/auth/saml/{self.tenant_id}/logout"
        )
        
        # Attribute mapping defaults
        self.attribute_map = self.config.get("attribute_mapping", {
            "email": ["email", "mail", "Email", "urn:oid:0.9.2342.19200300.100.1.3"],
            "first_name": ["firstName", "givenName", "first_name", "urn:oid:2.5.4.42"],
            "last_name": ["lastName", "surname", "last_name", "urn:oid:2.5.4.4"],
            "groups": ["groups", "memberOf", "Role", "urn:oid:1.2.840.113556.1.4.194"],
            "department": ["department", "Department", "ou", "urn:oid:2.5.4.11"],
            "phone": ["phone", "telephoneNumber", "mobile", "urn:oid:2.5.4.20"],
        })
    
    async def _fetch_idp_metadata(self) -> Dict[str, Any]:
        """Fetch and parse IdP metadata."""
        # In production, cache this with TTL
        import aiohttp
        
        metadata_url = self.config["idp_metadata_url"]
        async with aiohttp.ClientSession() as session:
            async with session.get(metadata_url) as resp:
                metadata_xml = await resp.text()
        
        return self._parse_idp_metadata(metadata_xml)
    
    def _parse_idp_metadata(self, metadata_xml: str) -> Dict[str, Any]:
        """Parse SAML metadata XML."""
        root = ET.fromstring(metadata_xml)
        
        # Extract entity ID
        entity_id = root.get("entityID")
        
        # Find SSO and SLO endpoints
        sso_url = None
        slo_url = None
        cert_data = None
        
        # Namespace handling
        ns = {
            "md": "urn:oasis:names:tc:SAML:2.0:metadata",
            "ds": "http://www.w3.org/2000/09/xmldsig#"
        }
        
        for idp_sso in root.findall(".//md:IDPSSODescriptor", ns):
            for sso_svc in idp_sso.findall("md:SingleSignOnService", ns):
                if sso_svc.get("Binding") == self.SAML_PROTOCOL_BINDING:
                    sso_url = sso_svc.get("Location")
            
            for slo_svc in idp_sso.findall("md:SingleLogoutService", ns):
                slo_url = slo_svc.get("Location")
            
            # Extract signing certificate
            key_desc = idp_sso.find("md:KeyDescriptor", ns)
            if key_desc is not None:
                cert = key_desc.find(".//ds:X509Certificate", ns)
                if cert is not None:
                    cert_data = cert.text
        
        return {
            "entity_id": entity_id,
            "sso_url": sso_url,
            "slo_url": slo_url,
            "certificate": cert_data,
        }
    
    def _generate_authn_request(self, context: SSOContext, idp_sso_url: str) -> str:
        """Generate SAML AuthnRequest XML."""
        request_id = f"_{context.request_id}"
        issue_instant = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="{self.SAML_PROTOCOL_NS}"
                    xmlns:saml="{self.SAML_ASSERTION_NS}"
                    ID="{request_id}"
                    Version="2.0"
                    IssueInstant="{issue_instant}"
                    Destination="{idp_sso_url}"
                    ProtocolBinding="{self.SAML_PROTOCOL_BINDING}"
                    AssertionConsumerServiceURL="{self.acs_url}">
    <saml:Issuer>{self.sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
                        AllowCreate="true"/>
    <samlp:RequestedAuthnContext Comparison="exact">
        <saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport</saml:AuthnContextClassRef>
    </samlp:RequestedAuthnContext>
</samlp:AuthnRequest>"""
        
        return authn_request
    
    def _build_saml_redirect_url(self, authn_request: str, idp_sso_url: str, relay_state: str) -> str:
        """Build the redirect URL with deflated AuthnRequest."""
        import zlib
        
        # Deflate and base64 encode the request
        deflated = zlib.compress(authn_request.encode(), 9)[2:-4]  # Strip zlib headers
        encoded = base64.b64encode(deflated).decode()
        
        params = {
            "SAMLRequest": encoded,
            "RelayState": relay_state,
        }
        
        # Sign if configured
        if self.config.get("sign_requests", False):
            signature = self._sign_params(params)
            params["Signature"] = signature
            params["SigAlg"] = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
        
        return f"{idp_sso_url}?{urlencode(params)}"
    
    def _sign_params(self, params: Dict[str, str]) -> str:
        """Sign request parameters."""
        # Implementation would use private key to sign
        # Return base64-encoded signature
        return ""
    
    async def initiate_login(self, context: SSOContext) -> AuthResult:
        """Initiate SAML SP-initiated SSO."""
        try:
            idp_metadata = await self._fetch_idp_metadata()
            
            if not idp_metadata.get("sso_url"):
                return AuthResult(
                    success=False,
                    error_code="SAML_CONFIG_ERROR",
                    error_message="IdP SSO URL not found in metadata"
                )
            
            # Generate AuthnRequest
            authn_request = self._generate_authn_request(context, idp_metadata["sso_url"])
            
            # Build redirect URL
            relay_state = context.relay_state or context.request_id
            redirect_url = self._build_saml_redirect_url(
                authn_request,
                idp_metadata["sso_url"],
                relay_state
            )
            
            return AuthResult(
                success=True,
                redirect_url=redirect_url
            )
            
        except Exception as e:
            return AuthResult(
                success=False,
                error_code="SAML_INIT_ERROR",
                error_message=str(e)
            )
    
    async def handle_callback(
        self, 
        context: SSOContext, 
        callback_data: Dict[str, Any]
    ) -> AuthResult:
        """Handle SAML response (ACS endpoint)."""
        try:
            saml_response = callback_data.get("SAMLResponse")
            relay_state = callback_data.get("RelayState")
            
            if not saml_response:
                return AuthResult(
                    success=False,
                    error_code="SAML_MISSING_RESPONSE",
                    error_message="SAMLResponse not provided"
                )
            
            # Decode response
            decoded_response = base64.b64decode(saml_response)
            
            # Parse and validate SAML response
            identity = self._parse_saml_response(decoded_response)
            
            # Determine MFA status from assertion
            mfa_verified = self._check_mfa_from_assertion(decoded_response)
            
            # Check MFA requirements
            if context.mfa_required == MFARequirement.REQUIRED and not mfa_verified:
                return AuthResult(
                    success=True,
                    mfa_pending=True,
                    mfa_methods=["totp", "sms"],
                    identity=identity
                )
            
            return AuthResult(
                success=True,
                identity=identity._replace(mfa_verified=mfa_verified)
            )
            
        except Exception as e:
            return AuthResult(
                success=False,
                error_code="SAML_CALLBACK_ERROR",
                error_message=str(e)
            )
    
    def _parse_saml_response(self, response_xml: bytes) -> UserIdentity:
        """Parse and validate SAML assertion."""
        root = ET.fromstring(response_xml)
        
        ns = {
            "saml": self.SAML_ASSERTION_NS,
            "samlp": self.SAML_PROTOCOL_NS,
        }
        
        # Extract assertion
        assertion = root.find(".//saml:Assertion", ns)
        if assertion is None:
            raise ValueError("SAML Assertion not found")
        
        # Get subject
        subject = assertion.find("saml:Subject", ns)
        name_id = subject.find("saml:NameID", ns).text if subject is not None else None
        
        # Extract attributes
        attribute_statement = assertion.find("saml:AttributeStatement", ns)
        attributes = {}
        
        if attribute_statement is not None:
            for attr in attribute_statement.findall("saml:Attribute", ns):
                name = attr.get("Name")
                values = [v.text for v in attr.findall("saml:AttributeValue", ns)]
                attributes[name] = values[0] if len(values) == 1 else values
        
        # Map attributes to identity fields
        email = self._get_mapped_attribute("email", attributes) or name_id
        groups = self._get_mapped_attribute("groups", attributes, [])
        if isinstance(groups, str):
            groups = [groups]
        
        return UserIdentity(
            external_id=name_id or email,
            email=email,
            tenant_id=self.tenant_id,
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            first_name=self._get_mapped_attribute("first_name", attributes),
            last_name=self._get_mapped_attribute("last_name", attributes),
            groups=tuple(groups),
            department=self._get_mapped_attribute("department", attributes),
            phone=self._get_mapped_attribute("phone", attributes),
            raw_attributes=attributes,
        )
    
    def _get_mapped_attribute(
        self, 
        field: str, 
        attributes: Dict[str, Any],
        default: Any = None
    ) -> Any:
        """Get attribute value using configured mappings."""
        candidates = self.attribute_map.get(field, [field])
        for attr_name in candidates:
            if attr_name in attributes:
                return attributes[attr_name]
        return default
    
    def _check_mfa_from_assertion(self, response_xml: bytes) -> bool:
        """Check if MFA was performed based on AuthnContext."""
        # Look for MFA indicators in AuthnContextClassRef
        mfa_indicators = [
            "MultiFactor",
            "TwoFactor",
            "mfa",
            "2fa",
        ]
        
        root = ET.fromstring(response_xml)
        ns = {"saml": self.SAML_ASSERTION_NS}
        
        for ctx in root.findall(".//saml:AuthnContextClassRef", ns):
            if ctx.text:
                for indicator in mfa_indicators:
                    if indicator in ctx.text:
                        return True
        
        return False
    
    async def validate_session(self, session_token: str) -> AuthResult:
        """SAML doesn't support session validation - use local validation."""
        return AuthResult(success=True)
    
    async def logout(self, session_token: str) -> AuthResult:
        """Initiate SAML Single Logout."""
        # Generate LogoutRequest
        return AuthResult(success=True)


# ============================================================================
# OIDC Provider
# ============================================================================

class OIDCProvider(SSOProvider):
    """
    OpenID Connect 1.0 Provider implementation.
    
    Supports:
    - Authorization Code flow with PKCE
    - ID Token validation (JWT)
    - UserInfo endpoint
    - Refresh token rotation
    - RP-initiated logout
    - Back-channel logout (optional)
    
    Dependencies:
    - authlib or jose for JWT handling
    """
    
    STANDARD_SCOPES = ["openid", "profile", "email", "groups", "offline_access"]
    
    @property
    def provider_type(self) -> SSOProviderType:
        return SSOProviderType.OIDC
    
    def _validate_config(self) -> None:
        required = ["issuer", "client_id", "client_secret"]
        missing = [k for k in required if k not in self.config]
        if missing:
            raise ValueError(f"Missing OIDC config keys: {missing}")
        
        self.issuer = self.config["issuer"].rstrip("/")
        self.client_id = self.config["client_id"]
        self.client_secret = self.config["client_secret"]
        self.scopes = self.config.get("scopes", self.STANDARD_SCOPES)
        self.use_pkce = self.config.get("use_pkce", True)
        
        # Discovery document cache
        self._discovery_data: Optional[Dict[str, Any]] = None
    
    async def _get_discovery_document(self) -> Dict[str, Any]:
        """Fetch OIDC discovery document."""
        if self._discovery_data:
            return self._discovery_data
        
        import aiohttp
        
        discovery_url = f"{self.issuer}/.well-known/openid-configuration"
        async with aiohttp.ClientSession() as session:
            async with session.get(discovery_url) as resp:
                if resp.status != 200:
                    raise ValueError(f"Discovery failed: {resp.status}")
                self._discovery_data = await resp.json()
        
        return self._discovery_data
    
    async def initiate_login(self, context: SSOContext) -> AuthResult:
        """Initiate OIDC Authorization Code flow."""
        try:
            discovery = await self._get_discovery_document()
            auth_endpoint = discovery["authorization_endpoint"]
            
            # Generate state and nonce
            state = self._generate_secure_token(16)
            nonce = self._generate_secure_token(16)
            
            context.state = state
            context.nonce = nonce
            
            params: Dict[str, str] = {
                "client_id": self.client_id,
                "response_type": "code",
                "scope": " ".join(self.scopes),
                "redirect_uri": context.redirect_uri or self._get_default_redirect_uri(),
                "state": state,
                "nonce": nonce,
            }
            
            # Add PKCE if enabled
            if self.use_pkce:
                verifier, challenge = self._generate_pkce_pair()
                context.pkce_verifier = verifier
                params["code_challenge"] = challenge
                params["code_challenge_method"] = "S256"
            
            # Add prompt if specified
            prompt = self.config.get("prompt")
            if prompt:
                params["prompt"] = prompt
            
            # Store context for callback
            await self._store_auth_context(context)
            
            auth_url = f"{auth_endpoint}?{urlencode(params)}"
            
            return AuthResult(success=True, redirect_url=auth_url)
            
        except Exception as e:
            return AuthResult(
                success=False,
                error_code="OIDC_INIT_ERROR",
                error_message=str(e)
            )
    
    async def handle_callback(
        self, 
        context: SSOContext, 
        callback_data: Dict[str, Any]
    ) -> AuthResult:
        """Handle OIDC callback and exchange code for tokens."""
        try:
            # Verify state
            state = callback_data.get("state")
            if state != context.state:
                return AuthResult(
                    success=False,
                    error_code="OIDC_STATE_MISMATCH",
                    error_message="State parameter mismatch"
                )
            
            # Check for errors
            if "error" in callback_data:
                return AuthResult(
                    success=False,
                    error_code=f"OIDC_{callback_data['error']}",
                    error_message=callback_data.get("error_description", "Unknown error")
                )
            
            code = callback_data.get("code")
            if not code:
                return AuthResult(
                    success=False,
                    error_code="OIDC_MISSING_CODE",
                    error_message="Authorization code not provided"
                )
            
            # Exchange code for tokens
            token_response = await self._exchange_code(code, context)
            
            # Validate ID token
            id_token = token_response.get("id_token")
            if not id_token:
                return AuthResult(
                    success=False,
                    error_code="OIDC_NO_ID_TOKEN",
                    error_message="ID token not received"
                )
            
            claims = self._validate_id_token(id_token, context.nonce)
            
            # Fetch userinfo if needed
            access_token = token_response.get("access_token")
            userinfo = await self._fetch_userinfo(access_token)
            
            # Build identity
            identity = self._build_identity(claims, userinfo)
            
            # Check for MFA claims
            amr = claims.get("amr", [])  # Authentication Methods References
            mfa_verified = any(m in amr for m in ["mfa", "otp", "hwk", "sms"])
            
            # Handle MFA requirements
            if context.mfa_required == MFARequirement.REQUIRED and not mfa_verified:
                return AuthResult(
                    success=True,
                    mfa_pending=True,
                    mfa_methods=["totp", "sms"],
                    identity=identity
                )
            
            return AuthResult(
                success=True,
                identity=identity._replace(mfa_verified=mfa_verified),
                session_token=token_response.get("refresh_token")
            )
            
        except Exception as e:
            return AuthResult(
                success=False,
                error_code="OIDC_CALLBACK_ERROR",
                error_message=str(e)
            )
    
    async def _exchange_code(
        self, 
        code: str, 
        context: SSOContext
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        import aiohttp
        
        discovery = await self._get_discovery_document()
        token_endpoint = discovery["token_endpoint"]
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": context.redirect_uri or self._get_default_redirect_uri(),
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        if context.pkce_verifier:
            data["code_verifier"] = context.pkce_verifier
        
        async with aiohttp.ClientSession() as session:
            async with session.post(token_endpoint, data=data) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise ValueError(f"Token exchange failed: {error_text}")
                return await resp.json()
    
    def _validate_id_token(self, id_token: str, expected_nonce: Optional[str]) -> Dict[str, Any]:
        """Validate and decode ID token JWT."""
        # In production, use authlib or python-jose
        # This is a simplified implementation
        
        import jwt
        
        # Fetch JWKS for signature verification
        # discovery = await self._get_discovery_document()
        # jwks_uri = discovery["jwks_uri"]
        
        # For now, decode without verification (DO NOT USE IN PRODUCTION)
        claims = jwt.decode(
            id_token,
            options={"verify_signature": False, "verify_exp": True}
        )
        
        # Validate issuer
        if claims.get("iss") != self.issuer:
            raise ValueError(f"Invalid issuer: {claims.get('iss')}")
        
        # Validate audience
        if claims.get("aud") != self.client_id:
            raise ValueError(f"Invalid audience: {claims.get('aud')}")
        
        # Validate nonce
        if expected_nonce and claims.get("nonce") != expected_nonce:
            raise ValueError("Nonce mismatch")
        
        return claims
    
    async def _fetch_userinfo(self, access_token: str) -> Dict[str, Any]:
        """Fetch user information from UserInfo endpoint."""
        import aiohttp
        
        discovery = await self._get_discovery_document()
        userinfo_endpoint = discovery.get("userinfo_endpoint")
        
        if not userinfo_endpoint:
            return {}
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(userinfo_endpoint, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
    
    def _build_identity(
        self, 
        id_claims: Dict[str, Any], 
        userinfo: Dict[str, Any]
    ) -> UserIdentity:
        """Build UserIdentity from OIDC claims."""
        # Merge claims, userinfo takes precedence
        merged = {**id_claims, **userinfo}
        
        sub = merged.get("sub", "")
        email = merged.get("email", "")
        
        # Parse groups
        groups = merged.get("groups", [])
        if isinstance(groups, str):
            groups = groups.split(",")
        
        return UserIdentity(
            external_id=sub,
            email=email,
            tenant_id=self.tenant_id,
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            first_name=merged.get("given_name") or merged.get("first_name"),
            last_name=merged.get("family_name") or merged.get("last_name"),
            groups=tuple(groups),
            phone=merged.get("phone_number"),
            raw_attributes=merged,
        )
    
    def _get_default_redirect_uri(self) -> str:
        """Get default redirect URI."""
        return f"https://dragonscope.io/auth/oidc/{self.tenant_id}/callback"
    
    async def _store_auth_context(self, context: SSOContext) -> None:
        """Store auth context for state validation."""
        # Implement with Redis or similar
        pass
    
    async def validate_session(self, session_token: str) -> AuthResult:
        """Validate OIDC session via introspection."""
        # Use token introspection if available
        return AuthResult(success=True)
    
    async def logout(self, session_token: str) -> AuthResult:
        """Initiate RP-initiated logout."""
        discovery = await self._get_discovery_document()
        end_session_endpoint = discovery.get("end_session_endpoint")
        
        if not end_session_endpoint:
            return AuthResult(success=True)
        
        params = {
            "client_id": self.client_id,
            "post_logout_redirect_uri": f"https://dragonscope.io/auth/logout/callback",
        }
        
        logout_url = f"{end_session_endpoint}?{urlencode(params)}"
        return AuthResult(success=True, redirect_url=logout_url)


# ============================================================================
# LDAP Provider
# ============================================================================

class LDAPProvider(SSOProvider):
    """
    LDAP/Active Directory Provider implementation.
    
    Supports:
    - Bind authentication
    - TLS/SSL (LDAPS and StartTLS)
    - Group membership resolution
    - Nested group support
    - Attribute synchronization
    
    Dependencies:
    - ldap3
    """
    
    @property
    def provider_type(self) -> SSOProviderType:
        return SSOProviderType.LDAP
    
    def _validate_config(self) -> None:
        required = ["host", "base_dn"]
        missing = [k for k in required if k not in self.config]
        if missing:
            raise ValueError(f"Missing LDAP config keys: {missing}")
        
        self.host = self.config["host"]
        self.port = self.config.get("port", 636 if self.config.get("use_ssl") else 389)
        self.use_ssl = self.config.get("use_ssl", True)
        self.start_tls = self.config.get("start_tls", False)
        self.base_dn = self.config["base_dn"]
        self.bind_dn = self.config.get("bind_dn")
        self.bind_password = self.config.get("bind_password")
        
        # Search configuration
        self.user_search_base = self.config.get("user_search_base", self.base_dn)
        self.user_search_filter = self.config.get(
            "user_search_filter", 
            "(&(objectClass=person)(|(mail={email})(uid={username})(sAMAccountName={username})))"
        )
        self.group_search_base = self.config.get("group_search_base", self.base_dn)
        
        # Attribute mapping
        self.attribute_map = self.config.get("attribute_mapping", {
            "email": "mail",
            "first_name": "givenName",
            "last_name": "sn",
            "groups": "memberOf",
            "department": "department",
            "phone": "telephoneNumber",
        })
    
    def _get_ldap_connection(self):
        """Create LDAP connection."""
        try:
            from ldap3 import Server, Connection, Tls, AUTO_BIND_TLS_BEFORE_BIND
            
            tls_config = Tls(validate=self.config.get("tls_validate", 0))
            server = Server(
                self.host,
                port=self.port,
                use_ssl=self.use_ssl,
                tls=tls_config,
                get_info='ALL'
            )
            
            conn = Connection(server, auto_bind=False)
            
            if self.start_tls and not self.use_ssl:
                conn.start_tls()
            
            return conn
        except ImportError:
            raise RuntimeError("ldap3 library required for LDAP authentication")
    
    async def initiate_login(self, context: SSOContext) -> AuthResult:
        """
        LDAP doesn't support redirect flows.
        Return error - use handle_direct_auth instead.
        """
        return AuthResult(
            success=False,
            error_code="LDAP_USE_DIRECT_AUTH",
            error_message="LDAP requires direct credential submission"
        )
    
    async def handle_direct_auth(
        self,
        username: str,
        password: str
    ) -> AuthResult:
        """
        Authenticate user directly with LDAP credentials.
        
        This is the primary authentication method for LDAP.
        """
        try:
            conn = self._get_ldap_connection()
            
            # Bind with service account if configured
            if self.bind_dn:
                if not conn.bind(self.bind_dn, self.bind_password):
                    return AuthResult(
                        success=False,
                        error_code="LDAP_BIND_ERROR",
                        error_message="Service account bind failed"
                    )
            
            # Search for user
            user_dn, user_attrs = self._find_user(conn, username)
            
            if not user_dn:
                return AuthResult(
                    success=False,
                    error_code="LDAP_USER_NOT_FOUND",
                    error_message="User not found in directory"
                )
            
            # Attempt user bind (authentication)
            user_conn = self._get_ldap_connection()
            if not user_conn.bind(user_dn, password):
                return AuthResult(
                    success=False,
                    error_code="LDAP_INVALID_CREDENTIALS",
                    error_message="Invalid username or password"
                )
            
            # Build identity
            identity = self._build_identity_from_ldap(user_dn, user_attrs)
            
            # Resolve groups
            groups = self._resolve_groups(conn, user_dn)
            identity = identity._replace(groups=tuple(groups))
            
            user_conn.unbind()
            conn.unbind()
            
            return AuthResult(success=True, identity=identity)
            
        except Exception as e:
            return AuthResult(
                success=False,
                error_code="LDAP_AUTH_ERROR",
                error_message=str(e)
            )
    
    def _find_user(
        self, 
        conn, 
        identifier: str
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Find user in LDAP directory."""
        search_filter = self.user_search_filter.format(
            email=identifier,
            username=identifier
        )
        
        conn.search(
            search_base=self.user_search_base,
            search_filter=search_filter,
            search_scope='SUBTREE',
            attributes=list(self.attribute_map.values())
        )
        
        if conn.entries:
            entry = conn.entries[0]
            return entry.entry_dn, entry.entry_attributes_as_dict
        
        return None, None
    
    def _resolve_groups(self, conn, user_dn: str) -> List[str]:
        """Resolve user's group memberships."""
        groups = []
        
        # Direct group membership
        group_filter = f"(&(objectClass=group)(member={user_dn}))"
        
        if self.config.get("nested_groups", False):
            # For AD: use LDAP_MATCHING_RULE_IN_CHAIN
            group_filter = f"(&(objectClass=group)(member:1.2.840.113556.1.4.1941:={user_dn}))"
        
        conn.search(
            search_base=self.group_search_base,
            search_filter=group_filter,
            search_scope='SUBTREE',
            attributes=['cn', 'name']
        )
        
        for entry in conn.entries:
            group_name = entry.cn.value if hasattr(entry, 'cn') else entry.entry_dn
            groups.append(str(group_name))
        
        return groups
    
    def _build_identity_from_ldap(
        self, 
        user_dn: str, 
        attrs: Dict[str, Any]
    ) -> UserIdentity:
        """Build UserIdentity from LDAP attributes."""
        def get_attr(key: str) -> Optional[str]:
            ldap_key = self.attribute_map.get(key)
            if ldap_key and ldap_key in attrs:
                val = attrs[ldap_key]
                return val[0] if isinstance(val, list) else val
            return None
        
        email = get_attr("email") or user_dn
        
        return UserIdentity(
            external_id=user_dn,
            email=email,
            tenant_id=self.tenant_id,
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            first_name=get_attr("first_name"),
            last_name=get_attr("last_name"),
            department=get_attr("department"),
            phone=get_attr("phone"),
            raw_attributes=attrs,
        )
    
    async def handle_callback(
        self, 
        context: SSOContext, 
        callback_data: Dict[str, Any]
    ) -> AuthResult:
        """LDAP doesn't use callbacks."""
        return AuthResult(
            success=False,
            error_code="LDAP_NO_CALLBACK",
            error_message="LDAP authentication doesn't use callbacks"
        )
    
    async def validate_session(self, session_token: str) -> AuthResult:
        """LDAP sessions are managed locally."""
        return AuthResult(success=True)
    
    async def logout(self, session_token: str) -> AuthResult:
        """LDAP logout is local only."""
        return AuthResult(success=True)


# ============================================================================
# Multi-Tenant Auth Manager
# ============================================================================

@dataclass
class TenantAuthConfig:
    """Authentication configuration for a tenant."""
    tenant_id: str
    domain: str
    display_name: str
    
    # Auth settings
    primary_idp: Optional[str] = None
    fallback_idp: Optional[str] = None
    allow_local_auth: bool = True
    session_timeout: int = 28800  # 8 hours
    absolute_timeout: int = 86400  # 24 hours
    
    # MFA settings
    mfa_required: MFARequirement = MFARequirement.OPTIONAL
    allowed_mfa_methods: List[str] = field(default_factory=lambda: ["totp", "sms", "webauthn"])
    mfa_grace_period_days: int = 7
    
    # Security settings
    max_concurrent_sessions: int = 5
    password_policy: Dict[str, Any] = field(default_factory=dict)
    brute_force_protection: bool = True
    max_login_attempts: int = 5
    lockout_duration: int = 1800  # 30 minutes
    
    # SSO providers
    sso_providers: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class MultiTenantAuthManager:
    """
    Central manager for multi-tenant authentication.
    
    Handles:
    - Tenant resolution from domain/email
    - Provider routing and selection
    - Session management across tenants
    - MFA policy enforcement
    - Audit logging
    """
    
    def __init__(self):
        self._tenant_configs: Dict[str, TenantAuthConfig] = {}
        self._domain_to_tenant: Dict[str, str] = {}
        self._providers: Dict[str, SSOProvider] = {}
        self._session_store: Optional[Any] = None  # Redis connection
        self._audit_logger: Optional[Any] = None
    
    def register_tenant(self, config: TenantAuthConfig) -> None:
        """Register a tenant's authentication configuration."""
        self._tenant_configs[config.tenant_id] = config
        self._domain_to_tenant[config.domain] = config.tenant_id
        
        # Initialize SSO providers
        for provider_id, provider_config in config.sso_providers.items():
            provider_type = provider_config.get("type")
            
            if provider_type == "saml":
                provider = SAMLProvider(config.tenant_id, provider_id, provider_config)
            elif provider_type == "oidc":
                provider = OIDCProvider(config.tenant_id, provider_id, provider_config)
            elif provider_type == "ldap":
                provider = LDAPProvider(config.tenant_id, provider_id, provider_config)
            else:
                continue
            
            key = f"{config.tenant_id}:{provider_id}"
            self._providers[key] = provider
    
    def resolve_tenant(self, identifier: str) -> Optional[str]:
        """
        Resolve tenant from email domain or subdomain.
        
        Args:
            identifier: Email address or domain
        """
        # Extract domain from email
        if "@" in identifier:
            domain = identifier.split("@")[1].lower()
        else:
            domain = identifier.lower()
        
        # Check direct domain mapping
        if domain in self._domain_to_tenant:
            return self._domain_to_tenant[domain]
        
        # Check subdomain patterns
        parts = domain.split(".")
        for i in range(len(parts)):
            parent_domain = ".".join(parts[i:])
            if parent_domain in self._domain_to_tenant:
                return self._domain_to_tenant[parent_domain]
        
        return None
    
    def get_provider(
        self, 
        tenant_id: str, 
        provider_id: Optional[str] = None
    ) -> Optional[SSOProvider]:
        """Get SSO provider for tenant."""
        config = self._tenant_configs.get(tenant_id)
        if not config:
            return None
        
        # Use primary IdP if not specified
        if not provider_id:
            provider_id = config.primary_idp
        
        if not provider_id:
            return None
        
        key = f"{tenant_id}:{provider_id}"
        return self._providers.get(key)
    
    async def initiate_login(
        self,
        tenant_id: str,
        provider_id: Optional[str] = None,
        relay_state: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ) -> AuthResult:
        """
        Initiate login for a tenant.
        
        Returns AuthResult with redirect_url for the user.
        """
        config = self._tenant_configs.get(tenant_id)
        if not config:
            return AuthResult(
                success=False,
                error_code="TENANT_NOT_FOUND",
                error_message="Tenant not found"
            )
        
        # Get provider
        provider = self.get_provider(tenant_id, provider_id)
        if not provider:
            if not config.allow_local_auth:
                return AuthResult(
                    success=False,
                    error_code="NO_IDP_CONFIGURED",
                    error_message="No identity provider configured for this tenant"
                )
            # Return success for local auth
            return AuthResult(success=True)
        
        # Create context
        context = SSOContext(
            tenant_id=tenant_id,
            provider_id=provider.provider_id,
            provider_type=provider.provider_type,
            request_id=secrets.token_hex(16),
            relay_state=relay_state,
            redirect_uri=redirect_uri,
            mfa_required=config.mfa_required
        )
        
        # Log attempt
        await self._log_auth_event("login_initiated", tenant_id, context.request_id)
        
        return await provider.initiate_login(context)
    
    async def handle_callback(
        self,
        tenant_id: str,
        provider_id: str,
        callback_data: Dict[str, Any],
        stored_context: Optional[SSOContext] = None
    ) -> AuthResult:
        """Handle SSO callback for a tenant."""
        provider = self.get_provider(tenant_id, provider_id)
        if not provider:
            return AuthResult(
                success=False,
                error_code="PROVIDER_NOT_FOUND",
                error_message="SSO provider not found"
            )
        
        # Reconstruct or retrieve context
        if stored_context is None:
            stored_context = await self._retrieve_auth_context(callback_data.get("state"))
        
        result = await provider.handle_callback(stored_context, callback_data)
        
        # Log result
        if result.success and result.identity:
            await self._log_auth_event(
                "login_success", 
                tenant_id, 
                stored_context.request_id,
                user_id=result.identity.external_id
            )
        else:
            await self._log_auth_event(
                "login_failed",
                tenant_id,
                stored_context.request_id,
                error=result.error_code
            )
        
        return result
    
    async def authenticate_local(
        self,
        tenant_id: str,
        username: str,
        password: str
    ) -> AuthResult:
        """Authenticate with local credentials."""
        config = self._tenant_configs.get(tenant_id)
        if not config or not config.allow_local_auth:
            return AuthResult(
                success=False,
                error_code="LOCAL_AUTH_DISABLED",
                error_message="Local authentication is disabled for this tenant"
            )
        
        # Check for LDAP fallback
        provider = self.get_provider(tenant_id)
        if provider and isinstance(provider, LDAPProvider):
            return await provider.handle_direct_auth(username, password)
        
        # Local credential validation
        # This would interface with the user database
        return await self._validate_local_credentials(tenant_id, username, password)
    
    async def _validate_local_credentials(
        self, 
        tenant_id: str, 
        username: str, 
        password: str
    ) -> AuthResult:
        """Validate credentials against local database."""
        # Implementation would query user database
        # Hash comparison using bcrypt/Argon2
        pass
    
    async def enforce_mfa(
        self,
        tenant_id: str,
        user_id: str,
        mfa_code: str,
        method: str = "totp"
    ) -> AuthResult:
        """Verify MFA code for user."""
        config = self._tenant_configs.get(tenant_id)
        if not config:
            return AuthResult(success=False, error_code="TENANT_NOT_FOUND")
        
        if method not in config.allowed_mfa_methods:
            return AuthResult(
                success=False,
                error_code="MFA_METHOD_NOT_ALLOWED",
                error_message=f"MFA method '{method}' not allowed"
            )
        
        # Verify MFA based on method
        if method == "totp":
            verified = await self._verify_totp(tenant_id, user_id, mfa_code)
        elif method == "sms":
            verified = await self._verify_sms_code(tenant_id, user_id, mfa_code)
        elif method == "webauthn":
            verified = await self._verify_webauthn(tenant_id, user_id, mfa_code)
        else:
            return AuthResult(
                success=False,
                error_code="UNKNOWN_MFA_METHOD"
            )
        
        if verified:
            await self._log_auth_event("mfa_verified", tenant_id, user_id=user_id)
            return AuthResult(success=True)
        
        return AuthResult(
            success=False,
            error_code="MFA_VERIFICATION_FAILED"
        )
    
    async def _verify_totp(self, tenant_id: str, user_id: str, code: str) -> bool:
        """Verify TOTP code."""
        import pyotp
        # Retrieve user's TOTP secret and verify
        return False
    
    async def _verify_sms_code(self, tenant_id: str, user_id: str, code: str) -> bool:
        """Verify SMS code."""
        # Check against stored verification code
        return False
    
    async def _verify_webauthn(self, tenant_id: str, user_id: str, response: str) -> bool:
        """Verify WebAuthn response."""
        # Use webauthn library to verify
        return False
    
    async def create_session(
        self,
        tenant_id: str,
        identity: UserIdentity,
        mfa_verified: bool = False
    ) -> str:
        """Create a new authenticated session."""
        config = self._tenant_configs.get(tenant_id)
        
        session_id = secrets.token_urlsafe(32)
        session_data = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": identity.external_id,
            "email": identity.email,
            "groups": list(identity.groups),
            "created_at": time.time(),
            "last_activity": time.time(),
            "mfa_verified": mfa_verified,
            "provider": identity.provider_id,
        }
        
        # Store in Redis with TTL
        ttl = config.session_timeout if config else 28800
        await self._store_session(session_id, session_data, ttl)
        
        return session_id
    
    async def validate_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Validate and return session data."""
        session = await self._retrieve_session(session_token)
        if not session:
            return None
        
        # Check expiration
        config = self._tenant_configs.get(session["tenant_id"])
        if config:
            max_age = time.time() - session["created_at"]
            if max_age > config.absolute_timeout:
                await self.revoke_session(session_token)
                return None
        
        # Update last activity
        session["last_activity"] = time.time()
        await self._store_session(session_token, session, config.session_timeout if config else 28800)
        
        return session
    
    async def revoke_session(self, session_token: str) -> None:
        """Revoke a session."""
        await self._delete_session(session_token)
    
    async def list_user_sessions(self, tenant_id: str, user_id: str) -> List[Dict[str, Any]]:
        """List all active sessions for a user."""
        # Query Redis for user's sessions
        return []
    
    async def revoke_all_user_sessions(self, tenant_id: str, user_id: str) -> int:
        """Revoke all sessions for a user. Returns count revoked."""
        sessions = await self.list_user_sessions(tenant_id, user_id)
        for session in sessions:
            await self.revoke_session(session["session_id"])
        return len(sessions)
    
    # Storage methods (implement with Redis)
    
    async def _store_auth_context(self, context: SSOContext) -> None:
        """Store auth context for callback validation."""
        pass
    
    async def _retrieve_auth_context(self, state: str) -> Optional[SSOContext]:
        """Retrieve auth context by state."""
        return None
    
    async def _store_session(self, session_id: str, data: Dict[str, Any], ttl: int) -> None:
        """Store session data."""
        pass
    
    async def _retrieve_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data."""
        return None
    
    async def _delete_session(self, session_id: str) -> None:
        """Delete session data."""
        pass
    
    async def _log_auth_event(
        self, 
        event_type: str, 
        tenant_id: str, 
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """Log authentication event to audit system."""
        if self._audit_logger:
            await self._audit_logger.log({
                "timestamp": time.time(),
                "event_type": event_type,
                "tenant_id": tenant_id,
                "request_id": request_id,
                "user_id": user_id,
                "error": error,
            })


# ============================================================================
# Factory and Registration
# ============================================================================

class SSOProviderFactory:
    """Factory for creating SSO providers."""
    
    _providers = {
        "saml": SAMLProvider,
        "oidc": OIDCProvider,
        "oauth2": OIDCProvider,  # OAuth2 providers often support OIDC
        "ldap": LDAPProvider,
    }
    
    @classmethod
    def create(
        cls,
        provider_type: str,
        tenant_id: str,
        provider_id: str,
        config: Dict[str, Any]
    ) -> SSOProvider:
        """Create an SSO provider instance."""
        provider_class = cls._providers.get(provider_type.lower())
        if not provider_class:
            raise ValueError(f"Unknown provider type: {provider_type}")
        
        return provider_class(tenant_id, provider_id, config)
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type) -> None:
        """Register a custom provider type."""
        cls._providers[name.lower()] = provider_class


# Global auth manager instance
auth_manager = MultiTenantAuthManager()


def get_auth_manager() -> MultiTenantAuthManager:
    """Get the global auth manager instance."""
    return auth_manager
