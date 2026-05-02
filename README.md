# shuck-shells

`shuck-shells` is the source repo for the shell archive index consumed by `shuck run`.

It owns:

- release assets for shell archives
- a generated `index.json` at the repo root
- automation to refresh that index from releases
- GitHub Pages publication for the generated JSON

## Release conventions

Releases are discovered from this repo's GitHub releases.

- release tag: `<shell>-<version>`
- archive asset: `<shell>-<version>-<platform>.tar.gz`

Examples:

- `bash-5.2.21`
- `zsh-5.9`
- `bash-5.2.21-x86_64-linux.tar.gz`

Supported shells:

- `bash`
- `zsh`
- `dash`
- `mksh`

Supported platforms:

- `x86_64-linux`
- `aarch64-linux`
- `x86_64-darwin`
- `aarch64-darwin`

## Published format

The generated `index.json` matches the schema currently consumed by `shuck-run`:

```json
{
  "version": 1,
  "shells": {
    "bash": {
      "versions": {
        "5.2.21": {
          "platforms": {
            "x86_64-linux": {
              "url": "https://...",
              "sha256": "..."
            }
          }
        }
      }
    }
  }
}
```

## Local development

Validate the checked-in index and the generator logic:

```bash
python3 scripts/validate_index.py index.json
python3 -m unittest discover -s tests
```

Rebuild the checked-in index from live releases in the current repository:

```bash
python3 scripts/build_index.py --output index.json
```

That mode uses `GITHUB_REPOSITORY` by default, or `--repo owner/name` to override it.

## Automation

- `refresh-index.yml` regenerates `index.json` nightly and opens or updates a PR if it changes.
- `validate.yml` validates the JSON schema, canonical ordering, and script tests on PRs and `main`.
- `publish-pages.yml` publishes the merged `index.json` to GitHub Pages.

The published endpoint for v1 is:

- `https://<owner>.github.io/shuck-shells/index.json`

## Required secrets

The automation uses separate GitHub actors for PR creation and approval:

- `SHUCK_SHELLS_PR_TOKEN`
- `SHUCK_SHELLS_APPROVER_TOKEN`

That split is intentional. GitHub does not allow a PR author to satisfy required approval on their own PR, so the approver token must belong to a different account than the PR author.
