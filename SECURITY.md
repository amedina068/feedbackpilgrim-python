# Security policy

## Report a security problem

Do not open a public issue for a security problem.

1. Go to the **Security** tab of this repository.
2. Click **Report a vulnerability**.
3. Write what the problem is, how to make it occur and which versions it affects.

GitHub keeps the report private in a security advisory. Only the maintainers can see it.

The maintainers will reply to the report. If the problem is real, they will make a fix and publish the security advisory.

## Supported versions

Only the newest release gets security fixes.

## Secrets

- The API token, the identity secret and the webhook signing secret are secrets.
- Make the identity hash only on a server. Never send the identity secret to a browser.
- The client does not show the token in `repr()`.
- The client does not follow redirects, so a redirect cannot send the token to another host.
- Do not put a token or a secret in an issue, a pull request, a log or a test fixture.
