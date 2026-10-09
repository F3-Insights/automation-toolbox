# Security

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. We aim to acknowledge a report within five business days.

Useful things to include: the file or script affected, what an attacker could do, and the steps to reproduce it.

## What counts

- A script that could leak a secret, write outside its Run folder, or send something without approval.
- A way for content an agent reads (an email, a document, a web page) to make a workflow take an action its boundaries forbid.
- A secret, credential or real personal data committed to the repository.

## How the toolbox handles secrets

- Scripts read secrets only from environment variables and never print them.
- Settings files hold no secrets; [docs/settings.md](docs/settings.md) lists every environment variable a script reads.
- The pre-commit check refuses secret-shaped strings, real email addresses and machine details.
- Agents never write to a live system directly; a finish step applies an approved change set, with its own safety checks.
