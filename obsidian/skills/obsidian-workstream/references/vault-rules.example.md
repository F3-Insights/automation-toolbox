# VAULT-RULES.md (example)

An invented example of the owner's vault rules. Copy it outside this repository, change every value, and point the setting `vault_rules` at the copy.

## Note kinds

### video

- title_prefix: `Video - `
- frontmatter:
  - `video_title`: the video's original title, verbatim, in quotes
  - `source`: the video's URL
  - `channel`: the channel name
  - `published`: the publish date, YYYY-MM-DD
  - `tags`: the list below
- tags: [video, unsorted]
- sections: My Takeaway, Executive Summary, then one section per theme

### podcast

- title_prefix: `Podcast - `
- frontmatter: `show`, `episode`, `listened` (YYYY-MM-DD), `tags`
- tags: [podcast]

## Vault gardener

- map_suffix: `Hub`
- placeholder: `TODO fill`
- never_file: `Archive`, `Media`
