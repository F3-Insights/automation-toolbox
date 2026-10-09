# IT access asks, and the reply that answers them

Two documents exchanged with a client's IT owner before any build starts. The consultant drafts both; the sponsor sends the first, IT sends the second. Used by `project-engagement-runbook` step 4 and step 8.

## The asks (consultant drafts, sponsor sends)

Opening line names the sponsor as sender and the consultant as drafter. Then a numbered list, most important first, each item one bold noun phrase and one or two sentences of exactly what is wanted and why:

1. **Integration app registration.** An app in your platform with two auth paths: a server-to-server credential for scheduled reads, and a delegated user flow for anything that writes on a person's behalf.
2. **Chat platform bot registration.** The app registration and bot resource needed to post into your team chat, scoped to one channel to start.
3. **Schema export.** From the admin console, an export of the objects and fields in the business application, so field names are known before any query is written.
4. **Edition and API limits.** Which edition you are on and roughly how much of the daily API allowance is already consumed, so a scheduled sync is sized to fit.
5. **Approval locks.** How your approval process is configured: does approval lock a record, and can an integration read locked records.
6. **Sandbox.** Whether a sandbox with the business application installed and licensed is available for development against non-production data.
7. **Change capture.** Whether you would allow change-data-capture or an automation flow on a few objects, so the sync is event-driven rather than polling.
8. **Native AI features.** Whether your edition includes the vendor's own AI or agent features, so the build does not duplicate what you already pay for.
9. **Other integrations.** What else currently reads or writes the application, so the new one follows the same patterns and does not collide.
10. **Data location.** Any constraints on where synced project and financial data may be stored or processed.

Close with a one-line offer of a 30-minute call to walk through them.

## The reply IT is likely to send back (draft it so they can edit rather than write)

Five questions, each answered in two or three sentences:

1. **Use cases and data.** What the integration does and which objects and fields it touches, read versus write.
2. **Tooling.** What runs where: hosted by whom, on what, reachable how.
3. **Safeguards.** Human approval before writes, logging, rate limits, what happens on error, how it is switched off.
4. **Where the code lives.** Repository, who has access, how changes are reviewed.
5. **Access requested.** The minimum set from the asks list above, with the least privilege that works, and what can wait until later.
