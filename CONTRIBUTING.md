# Contributing

Thanks for helping improve the toolbox. Issues, fixes and new pieces are all welcome.

## Before you start

- **Open an issue first** for a new agent, skill or department, so we can agree where it belongs before you write it.
- Read [CONTEXT.md](CONTEXT.md) for the vocabulary and [docs/adr/](docs/adr/) for the decisions the repository is built on.

## The rules a change must follow

- **One home per piece.** Every agent and skill lives in exactly one department. There is no shared folder; other pieces refer to it by name.
- **Names are unique across the repository.** The check enforces it.
- **Agents follow one template**: an opening sentence, then Goal, Inputs, Context, Approach, Boundaries, Done when and Output. Start from [templates/](templates/).
- **Scripts live in the skill that owns them**, in `scripts/`, import only the standard library, a few named packages and files in their own folder, and ship with tests in `scripts/tests/`.
- **Invented examples only.** No real people, companies, clients, addresses, account numbers or figures, in prose, fixtures or tests. Swapping a real name is not enough: rewrite any example someone could trace back to real work.
- **Nothing owner-specific.** Folders, thresholds and preferences are settings or rules files, never facts in the repository. Add any new setting to [docs/settings.md](docs/settings.md).
- **No model writes to a live system.** Writes go into a change set that a finish step applies after approval.
- **Markdown style**: one paragraph or list item per line, no hard wraps.

## Checking your change

```bash
git config core.hooksPath .githooks
python3 scripts/toolbox_check.py
.venv/bin/python scripts/run_tests.py <department>
```

The pre-commit hook runs the check; a pull request should also pass the tests of every skill it touches.

## Pull requests

- Keep each pull request to one piece or one concern.
- Say what changed, why, and how you checked it.
- Update the department README (and its "Needs" column) when a piece's requirements change.

## License of contributions

The toolbox is published under the [PolyForm Shield License 1.0.0](LICENSE). By opening a pull request, you confirm that you have the right to contribute the change and agree that it is licensed under the same terms, and that F3 Insights may also offer it under other license terms.

Third-party material needs its upstream, license and notice recorded in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md), with the license file kept in the adapted skill's folder.
