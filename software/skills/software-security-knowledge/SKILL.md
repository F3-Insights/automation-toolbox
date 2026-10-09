---
name: software-security-knowledge
description: "Reference loaded alongside the built-in security-review skill or software-review, not for a user request: security patterns and stack-specific checks for Supabase, FastAPI and Express, with the OWASP code-level patterns and severity criteria behind them. Consult it before a security pass on a diff or a repository."
user-invocable: false
---

# Security knowledge

Reference material: security patterns, framework-specific checks, and the severity criteria that keep a rating honest.

The scanning itself is no longer a home-built pipeline. Use the built-in `security-review` skill over a diff, and the `claude-security` plugin for a repository sweep. Read this file first so the pass knows what to look for in the stacks covered here: Supabase, FastAPI and Express. The `software-review` skill, which the software factory's reviewer follows, points its security pass here for exactly that reason.

## OWASP Top 10 (2021): Code-Level Patterns

### A01: Broken Access Control
- Missing auth middleware on routes
- Direct object reference without ownership check (`/api/users/:id` without verifying the caller IS that user)
- Role checks in frontend only (not enforced server-side)
- Missing RLS policies on Supabase tables

### A02: Cryptographic Failures
- Hardcoded secrets in source code
- Weak hashing (MD5, SHA1 for passwords)
- Missing encryption for sensitive data at rest
- HTTP links for sensitive operations (should be HTTPS)

### A03: Injection
- SQL: String concatenation in queries (`SELECT * FROM users WHERE id = '${id}'`)
- XSS: `dangerouslySetInnerHTML`, `v-html`, `|safe` with user input
- Command: `exec()`, `os.system()`, `subprocess.run(shell=True)` with user input
- Template: User input in template strings rendered server-side

### A04: Insecure Design
- No rate limiting on auth endpoints
- No account lockout after failed attempts
- Password reset tokens that don't expire
- Missing CSRF protection on state-changing requests

### A05: Security Misconfiguration
- CORS `Access-Control-Allow-Origin: *` with credentials
- Debug mode in production
- Default credentials in deployment configs
- Unnecessary services/ports exposed

### A06: Vulnerable Components
- Known CVEs in direct dependencies
- Unmaintained packages with open security issues
- Using deprecated/sunset APIs

### A07: Authentication Failures
- Weak password requirements (no minimum length/complexity)
- Missing brute-force protection
- Session fixation (not rotating session ID after login)
- JWT with `none` algorithm accepted

### A08: Data Integrity Failures
- Deserialization of untrusted data without validation
- Missing integrity checks on CI/CD pipelines
- Auto-update without signature verification

### A09: Logging Failures
- Passwords/tokens in log output
- No audit trail for admin actions
- Missing logging for auth failures

### A10: SSRF
- User-provided URLs fetched server-side without allowlist
- Internal service URLs accessible via user input
- DNS rebinding not considered

## Supabase-Specific Security

### Service Role Key
- **CRITICAL if exposed client-side**: `service_role` key bypasses ALL RLS policies
- Safe locations: server-side only (API routes, edge functions, server components)
- Unsafe locations: any file that ships to the browser (components, client-side utils)
- Pattern to find: `supabase.createClient(url, service_role_key)` in client code

### Anon Key
- Safe client-side: this is expected and designed
- The anon key respects RLS policies
- Only dangerous if RLS is not properly configured

### RLS (Row Level Security)
- Every table with user data MUST have RLS enabled
- Common mistake: creating a table and forgetting to enable RLS
- Check: `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` or Supabase dashboard settings
- Policies should use `auth.uid()` not hardcoded user IDs
- SELECT, INSERT, UPDATE, DELETE should each have appropriate policies

### Edge Functions
- Verify they check auth before processing
- Check for CORS configuration on edge functions

## FastAPI-Specific Security

### Dependency Injection Auth
- Auth should be a dependency, not checked manually in each route
- `Depends(get_current_user)` pattern is correct
- Missing `Depends()` on a route is a potential auth bypass

### Pydantic Validation
- Pydantic v2 validates by default: this is good
- Watch for `model_config = {"strict": False}` overrides
- Check that response models don't leak sensitive fields

### CORS Middleware
- `CORSMiddleware` should have explicit `allow_origins`, not `["*"]`
- `allow_credentials=True` with `allow_origins=["*"]` is a security issue

## Node.js/Express-Specific Security

### Helmet
- Should be present: `app.use(helmet())` sets security headers
- Missing Helmet is MEDIUM severity for web apps

### Rate Limiting
- `express-rate-limit` or similar should protect auth endpoints
- Missing rate limiting on `/login`, `/signup`, `/forgot-password` is HIGH

### Body Parser Limits
- Default body-parser has no size limit: potential DoS
- Should have: `express.json({ limit: '10mb' })` or appropriate limit

### express-validator
- User input should be validated before use
- Check for `body()`, `param()`, `query()` validators on routes

## Common Secret Regex Patterns

```
# AWS
AKIA[A-Z0-9]{16}
aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}

# Stripe
sk_live_[a-zA-Z0-9]{24,}
sk_test_[a-zA-Z0-9]{24,}

# GitHub
ghp_[a-zA-Z0-9]{36}
gho_[a-zA-Z0-9]{36}
github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}

# Slack
xoxb-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}
xoxp-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,}

# Generic
-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----
password\s*[:=]\s*["'][^"']{8,}["']
(api_key|apikey|api_secret|secret_key|access_token)\s*[:=]\s*["'][^"']+["']

# Supabase
eyJ[a-zA-Z0-9_-]{100,}  (long JWT: check if it's service_role)
service_role
```

## Severity Guidelines

| Finding | Typical Severity |
|---------|-----------------|
| Hardcoded production secret in source | CRITICAL |
| service_role key in client-side code | CRITICAL |
| SQL injection with user input | CRITICAL |
| Missing auth on data-modifying endpoint | CRITICAL |
| Missing RLS on table with user data | CRITICAL |
| Auth token in localStorage | HIGH |
| Missing rate limiting on auth endpoints | HIGH |
| CORS wildcard with credentials | HIGH |
| Debug mode in production config | HIGH |
| XSS via dangerouslySetInnerHTML | HIGH |
| Missing security headers (web app) | MEDIUM |
| Outdated security-critical dependency | MEDIUM |
| Missing CSRF protection | MEDIUM |
| Running Docker container as root | MEDIUM |
| Missing lock file | MEDIUM |
| .env not in .gitignore | MEDIUM |
| Weak password policy | LOW |
| Missing MFA support | LOW |
| Test secrets in test fixtures | INFO |
| Anon key in client-side code (Supabase) | INFO |
