# Authenticated password changes

The header's **Şifre Değiştir** button opens a form requiring the current
password, a new password (15–128 characters), and confirmation. The API verifies
the current password independently of the browser. A conditional SQL update
prevents concurrent changes from silently overwriting one another. Passwords
are not returned in successful or rejected password-change responses.

`POST /api/auth/change-password` requires a Bearer session and enforces shared
Redis limits of 5 attempts/minute and 20/hour per authenticated user. Existing
registration/login behavior and password hash format are preserved. Hash
comparison uses `hmac.compare_digest`.

JWTs now carry an HMAC credential stamp derived from the current stored password
hash. Every authenticated request checks it against the database. Changing the
password invalidates all previously issued sessions for that account. No schema
migration or JWT secret rotation is needed. The browser clears its session after
success and requests a fresh login.

## Deployment impact

Previously issued JWTs lack the stamp and are rejected after this release.
**All existing users must sign in once again after deployment.** Users, portfolio
records and watchlists are preserved. The feature is not live until the commit
is pushed and Coolify redeploy completes. It does not change passwords by itself.
Do not enter or share a real password in deployment logs, CLI arguments, Git or
screenshots. This is an authenticated change flow, not forgotten-password recovery.

## Validation

- Six new API integration checks cover current-password verification, password
  length and equality checks, unauthorized/legacy sessions, simultaneous-change
  conflicts, old/new-password login, session invalidation and Redis rate limits.
- The API checks use a database double; real shared Redis counters are isolated
  by random client/user keys and only those test keys are removed.
- All 32 backend regression checks pass.
- The production frontend Docker build passes. Live browser acceptance remains:
  sign in, change password, confirm logout, then sign in with the new password.

## Google warning

Search Console reports possible phishing on user login with no sample URLs.
The owner confirmed reusing a password saved for another site. That is consistent
with the password-reuse warning, but does not prove a false positive or establish
that the entire deployment is secure. Password fields now provide explicit
username/current-password/new-password autocomplete hints. These changes do not
guarantee removal of Google's warning. Do not disable browser protections or
claim that a security review has already succeeded.
