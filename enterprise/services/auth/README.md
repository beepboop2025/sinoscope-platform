# DragonScope Enterprise Authentication & SSO

Enterprise-grade authentication system supporting multi-tenant architectures, Single Sign-On (SSO), and Multi-Factor Authentication (MFA).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DragonScope Auth Service                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │   SAML 2.0   │  │    OIDC      │  │    LDAP      │  SSO Layer   │
│  │   Provider   │  │   Provider   │  │   Provider   │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              MultiTenantAuthManager                          │    │
│  │  - Tenant isolation  - Identity provider routing  - Sessions │    │
│  └─────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              JWT Token Architecture                          │    │
│  │  - Access tokens (short-lived)  - Refresh tokens (rotating)  │    │
│  │  - Tenant-scoped claims  - Permission embedding              │    │
│  └─────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │     MFA      │  │     RBAC     │  │    Audit     │               │
│  │   Service    │  │   Engine     │  │   Logger     │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

## Multi-Tenant Authentication

### Tenant Isolation Model

```
┌─────────────────────────────────────────────────────────┐
│                    DragonScope Platform                  │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │  Tenant A   │  │  Tenant B   │  │  Tenant C   │      │
│  │  (Acme Corp)│  │  (Globex)   │  │  (Initech)  │      │
│  │             │  │             │  │             │      │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │      │
│  │ │IdP: Okta│ │  │ │IdP: Azure│ │  │ │IdP: AD  │ │      │
│  │ │Users:500│ │  │ │Users:2K │ │  │ │Users:50│ │      │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │      │
│  │             │  │             │  │             │      │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │      │
│  │ │MFA: TOTP│ │  │ │MFA: SMS │ │  │ │MFA: Yubi│ │      │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

### Tenant Configuration

```python
{
    "tenant_id": "tenant_acme_corp_001",
    "domain": "acme.dragonscope.io",
    "display_name": "Acme Corporation",
    "auth_config": {
        "primary_idp": "saml_okta",
        "fallback_idp": "oidc_google",
        "allow_local_auth": false,
        "session_timeout": 28800,  # 8 hours
        "mfa_required": true,
        "mfa_methods": ["totp", "webauthn"]
    },
    "sso_providers": [
        {
            "type": "saml",
            "id": "saml_okta",
            "metadata_url": "https://acme.okta.com/app/...",
            "attribute_mapping": {...}
        }
    ]
}
```

## SSO Providers

### SAML 2.0 Provider

Supports enterprise identity providers including:
- Okta
- Azure AD / Entra ID
- Ping Identity
- OneLogin
- ADFS (Active Directory Federation Services)

**Features:**
- SP-initiated and IdP-initiated SSO
- Encrypted assertions
- Signed requests and responses
- Attribute mapping for user provisioning
- Just-In-Time (JIT) provisioning

```python
from dragonscope.enterprise.auth.sso import SAMLProvider

saml_provider = SAMLProvider(
    tenant_id="acme_corp",
    config={
        "entity_id": "https://dragonscope.io/auth/saml",
        "idp_metadata_url": "https://acme.okta.com/app/...",
        "want_assertions_signed": True,
        "want_name_id_encrypted": True,
    }
)
```

### OIDC Provider

Supports OpenID Connect 1.0 providers:
- Google Workspace
- Microsoft Azure AD
- Auth0
- Keycloak
- Custom OIDC servers

**Features:**
- Authorization Code flow with PKCE
- ID Token validation
- Userinfo endpoint integration
- Refresh token rotation
- Logout (RP-initiated and back-channel)

```python
from dragonscope.enterprise.auth.sso import OIDCProvider

oidc_provider = OIDCProvider(
    tenant_id="acme_corp",
    config={
        "issuer": "https://accounts.google.com",
        "client_id": "...",
        "client_secret": "...",
        "scopes": ["openid", "profile", "email"],
    }
)
```

### LDAP Provider

Supports directory services:
- Active Directory
- OpenLDAP
- FreeIPA
- Oracle Internet Directory

**Features:**
- LDAPS and StartTLS
- Bind authentication
- Group membership resolution
- Nested group support
- Attribute synchronization

```python
from dragonscope.enterprise.auth.sso import LDAPProvider

ldap_provider = LDAPProvider(
    tenant_id="acme_corp",
    config={
        "host": "ldap.acme.com",
        "port": 636,
        "use_ssl": True,
        "base_dn": "dc=acme,dc=com",
        "bind_dn": "cn=service,dc=acme,dc=com",
    }
)
```

## Multi-Factor Authentication (MFA)

### TOTP (Time-based One-Time Password)

- RFC 6238 compliant
- Compatible with Google Authenticator, Authy, Microsoft Authenticator
- QR code enrollment
- Backup codes for recovery

### SMS Authentication

- Twilio and AWS SNS integrations
- Rate limiting per phone number
- International number support
- Fallback to voice calls

### Hardware Security Keys (WebAuthn)

- FIDO2/WebAuthn compliant
- Support for YubiKey, Titan Security Key, etc.
- Platform authenticators (Touch ID, Windows Hello)
- Resident key support

### MFA Enforcement Policies

```python
{
    "mfa_policy": {
        "required_for_roles": ["admin", "analyst", "operator"],
        "required_for_actions": ["delete", "export", "invite_user"],
        "grace_period_days": 7,
        "allowed_methods": ["totp", "webauthn", "sms"],
        "backup_codes_count": 10
    }
}
```

## JWT Token Architecture

### Token Types

#### Access Token (Short-lived: 15 minutes)

```json
{
  "jti": "tok_1234567890",
  "sub": "user_abc123",
  "tid": "tenant_acme_001",
  "iss": "https://auth.dragonscope.io",
  "aud": "https://api.dragonscope.io",
  "iat": 1704067200,
  "exp": 1704068100,
  "scope": "terminals:read terminals:write",
  "permissions": ["terminal.view", "terminal.connect", "logs.read"],
  "roles": ["analyst"],
  "session_id": "sess_xyz789",
  "mfa_verified": true,
  "auth_time": 1704067100
}
```

#### Refresh Token (Long-lived: 7 days, rotating)

```json
{
  "jti": "refr_9876543210",
  "sub": "user_abc123",
  "tid": "tenant_acme_001",
  "iss": "https://auth.dragonscope.io",
  "aud": "https://auth.dragonscope.io",
  "iat": 1704067200,
  "exp": 1704672000,
  "token_family": "fam_abc123xyz",
  "rotation_count": 0
}
```

### Token Security

- RS256 asymmetric signing (2048-bit RSA)
- JWK key rotation every 24 hours
- Token binding to prevent theft
- Automatic revocation on security events

## RBAC (Role-Based Access Control)

### Role Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                      Organization Admin                      │
│                    (Full platform access)                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Tenant Admin   │    │ Security Admin │    │ Billing Admin  │
│                │    │                │    │                │
│ - User Mgmt    │    │ - Policies     │    │ - Invoices     │
│ - Settings     │    │ - Audit Logs   │    │ - Plans        │
│ - SSO Config   │    │ - Alerts       │    │ - Usage        │
└───────┬───────┘    └───────────────┘    └───────────────┘
        │
        ├──────────────┬──────────────┬──────────────┐
        │              │              │              │
        ▼              ▼              ▼              ▼
┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│  Analyst   │  │ Operator   │  │  Viewer    │  │  API Key   │
│            │  │            │  │            │  │            │
│ - Connect  │  │ - Execute  │  │ - View     │  │ - Limited  │
│ - Analyze  │  │ - Schedule │  │ - Export   │  │ - Scoped   │
│ - Report   │  │ - Monitor  │  │ - Search   │  │ - No UI    │
└───────────┘  └───────────┘  └───────────┘  └───────────┘
```

### Permission Granularity

500+ granular permissions covering:
- Terminal operations (connect, execute, upload, download)
- Fleet management (create, edit, delete, tag)
- User management (invite, suspend, role assignment)
- Security policies (configure MFA, set password rules)
- Audit and compliance (view logs, export reports)
- API and integrations (manage keys, webhooks)

## API Endpoints

### Authentication

```
POST /auth/login              # Local authentication
POST /auth/sso/initiate       # Initiate SSO flow
POST /auth/sso/callback       # SSO callback
POST /auth/mfa/verify         # Verify MFA code
POST /auth/token/refresh      # Refresh access token
POST /auth/logout             # Revoke tokens
```

### Session Management

```
GET    /auth/sessions         # List active sessions
DELETE /auth/sessions/{id}    # Revoke specific session
DELETE /auth/sessions/all     # Revoke all sessions
```

### MFA Management

```
POST   /auth/mfa/enable       # Enable MFA method
DELETE /auth/mfa/{method}     # Disable MFA method
POST   /auth/mfa/backup-codes # Generate backup codes
GET    /auth/mfa/status       # Get MFA status
```

## Configuration

### Environment Variables

```bash
# JWT Configuration
AUTH_JWT_PRIVATE_KEY_PATH=/etc/dragonscope/keys/jwt-private.pem
AUTH_JWT_PUBLIC_KEY_PATH=/etc/dragonscope/keys/jwt-public.pem
AUTH_JWT_ACCESS_TOKEN_TTL=900
AUTH_JWT_REFRESH_TOKEN_TTL=604800

# SSO Configuration
AUTH_SAML_CERT_PATH=/etc/dragonscope/certs/saml.crt
AUTH_SAML_KEY_PATH=/etc/dragonscope/certs/saml.key

# MFA Configuration
AUTH_MFA_TOTP_ISSUER=DragonScope
AUTH_MFA_SMS_PROVIDER=twilio
AUTH_MFA_RATE_LIMIT_PER_MINUTE=5

# Session Configuration
AUTH_SESSION_MAX_CONCURRENT=5
AUTH_SESSION_ABSOLUTE_TIMEOUT=28800
```

## Security Considerations

1. **Tenant Isolation**: Strict data separation between tenants
2. **Rate Limiting**: Per-tenant and per-user rate limits
3. **Audit Logging**: All authentication events logged
4. **Brute Force Protection**: Account lockout after failed attempts
5. **Session Security**: Secure, httpOnly, sameSite cookies
6. **Token Binding**: Cryptographic binding to client
7. **Secrets Management**: Integration with HashiCorp Vault, AWS Secrets Manager

## Integration Guide

### Frontend Integration

```javascript
// Initialize auth client
const auth = new DragonScopeAuth({
  tenantId: 'acme_corp',
  redirectUri: 'https://acme.dragonscope.io/auth/callback'
});

// Initiate SSO login
await auth.loginWithSSO('saml_okta');

// Or local login with MFA
const session = await auth.login({
  email: 'user@acme.com',
  password: '...'
});

if (session.requiresMFA) {
  const mfaCode = await promptForMFA();
  await auth.verifyMFA(mfaCode);
}
```

### Backend Integration

```python
from dragonscope.enterprise.auth.middleware import require_auth, require_permission

@app.route('/api/terminals')
@require_auth()
@require_permission('terminal.list')
def list_terminals():
    # Access token validated, user has permission
    tenant_id = g.current_user.tenant_id
    return TerminalService.list(tenant_id)
```

## Compliance

- **SOC 2 Type II**: Security controls and monitoring
- **ISO 27001**: Information security management
- **GDPR**: Data protection and right to deletion
- **HIPAA**: Optional BAA for healthcare customers
