# Contributing to shuck-shells

This repo owns:

- release assets for shell archives
- shell source metadata in `shells.json`
- generated registry JSON documents under `registry/`
- CI workflows that build and publish shell release archives
- automation that refreshes the index from releases
- GitHub Pages publication for the generated JSON

## Local development

Validate the checked-in index and the generator logic:

```bash
python3 scripts/validate_index.py registry
python3 -m unittest discover -s tests
python3 scripts/discover_upstream_versions.py --pretty --repo owner/name
bash -n scripts/build_shell_release.sh
bash -n scripts/build_bash_release.sh
bash -n scripts/build_busybox_release.sh
bash -n scripts/build_dash_release.sh
bash -n scripts/build_mksh_release.sh
bash -n scripts/build_zsh_release.sh
bash -n scripts/verify_source_sha256.sh
```

Rebuild the checked-in index from live releases in the current repository:

```bash
python3 scripts/build_index.py --output-dir registry
```

That mode uses `GITHUB_REPOSITORY` by default, or `--repo owner/name` to override it.

## Shell catalog

`shells.json` is the planning seam for where release assets come from.

Each shell entry declares:

- a display name
- a `release_source.kind`
- for buildable shells, the builder script used by the release workflow
- for GitHub-release shells, the upstream repo plus tag and asset matching rules
- upstream discovery metadata for automatic version detection
- expected upstream source SHA-256 values for buildable shell versions

Current release sources:

- repo-produced archives: `bash`, `busybox`, `dash`, `mksh`, `zsh`
- GitHub releases: `bashkit` (`everruns/bashkit`), `gbash` (`ewhauser/gbash`)

The catalog drives both paths, so the registry can mix repo-built shells with externally released shells without changing the published JSON format.

## Building shell archives

`shuck-shells` builds and publishes `bash`, `busybox`, `dash`, `mksh`, and `zsh` archives itself. Most come from upstream source tarballs; BusyBox is repackaged from Docker BusyBox rootfs archives.

- workflow: `.github/workflows/build-shell-release.yml`
- trigger: manual `workflow_dispatch`
- inputs:
  - `shell`
  - `version`

The workflow only builds shells whose `release_source.kind` is `build`. If a later shell is cataloged under another source kind, the workflow fails fast instead of pretending to support it.

Buildable versions must also have an expected upstream source digest in `upstream.source_sha256s`. The release workflow verifies the downloaded upstream archive against that digest before extracting or compiling it. If discovery finds a newer upstream version without a cataloged digest, the nightly job reports it but does not dispatch a build.

The workflow performs a release preflight check before starting the matrix:

- if the `<shell>-<version>` release does not exist yet, it builds the shell's supported platform archives
- if the published release exists but is missing one or more expected supported-platform assets, it fails instead of mutating release assets
- if the release already has the full expected asset set, it exits before running the build matrix

Release immutability is enabled for this repository. New releases are created as drafts, checked for the full expected asset set, and then published. After publication, tags and assets are not expected to be modified.

### Buildable shells

- `bash`
  - builder: `scripts/build_bash_release.sh`
  - source tarball: `https://ftp.gnu.org/pub/gnu/bash/bash-<version>.tar.gz`
- `busybox`
  - builder: `scripts/build_busybox_release.sh`
  - discovery metadata: `https://raw.githubusercontent.com/docker-library/official-images/master/library/busybox`
  - input rootfs: `https://raw.githubusercontent.com/docker-library/busybox/<commit>/<directory>/rootfs.tar.gz`
  - runtime packaging: extracts `/bin/busybox`, then wraps it so `bin/busybox` runs the bundled `sh` applet
  - supported platforms: musl only (`x86_64-linux-musl`, `aarch64-linux-musl`)
  - note: the Docker BusyBox glibc rootfs binaries currently require `GLIBC_2.38`, which is newer than this repo's Ubuntu 22.04 GNU baseline, so `*-linux-gnu` assets are intentionally not published
- `dash`
  - builder: `scripts/build_dash_release.sh`
  - source archive: `https://kernel.googlesource.com/pub/scm/utils/dash/dash/+archive/refs/tags/v<version>.tar.gz`
  - discovery source: `https://kernel.googlesource.com/pub/scm/utils/dash/dash/`
- `mksh`
  - builder: `scripts/build_mksh_release.sh`
  - source tarball: `https://mbsd.evolvis.org/MirOS/dist/mir/mksh/mksh-<version>.tgz`
  - version format: upstream release names include the leading `R`, for example `R59c`
- `zsh`
  - builder: `scripts/build_zsh_release.sh`
  - source tarball: `https://downloads.sourceforge.net/project/zsh/zsh/<version>/zsh-<version>.tar.xz`

### Runner matrix

The workflow currently builds on these GitHub-hosted runner labels:

- `ubuntu-22.04`
- `ubuntu-22.04-arm`
- `macos-15-intel`
- `macos-15`

The Linux matrix intentionally splits glibc and musl:

- `*-linux-gnu` archives are built natively on Ubuntu 22.04 runners, so their runtime compatibility follows that glibc baseline.
- `*-linux-musl` archives are built inside Alpine and target musl-based systems.

The release tag format stays `<shell>-<version>`, so:

- a Bash build for `5.2.21` publishes or updates `bash-5.2.21`
- a BusyBox build for `1.37.0` publishes or updates `busybox-1.37.0`
- a dash build for `0.5.13.2` publishes or updates `dash-0.5.13.2`
- an mksh build for `R59c` publishes or updates `mksh-R59c`
- a Zsh build for `5.9` publishes or updates `zsh-5.9`

## External GitHub releases

Some shells are indexed directly from their own GitHub releases instead of being built in this repo.

- `bashkit`
  - repo: `everruns/bashkit`
  - tag format: `v<version>`
  - indexed assets: Darwin tarballs plus Linux GNU tarballs when present
- `gbash`
  - repo: `ewhauser/gbash`
  - tag format: `v<version>`
  - indexed assets: `gbash_<version>_{linux,darwin}_{amd64,arm64}.tar.gz`
  - ignored assets: `gbash-extras_*`, Windows archives, and other non-runtime side assets

These shells are pulled in by the registry refresh job. They are not built or republished by `shuck-shells`.

## Automation

- `refresh-index.yml` regenerates the checked-in registry tree nightly and opens or updates a PR if it changes. It also runs automatically when a new shell release is published, and fetches configured external GitHub-release shells during its nightly regeneration pass.
- `discover-upstream.yml` checks upstream release pages nightly and dispatches `build-shell-release.yml` for any missing latest shell releases.
- `validate.yml` validates the JSON schema, canonical ordering, and script tests on PRs and `main`.
- `publish-pages.yml` publishes the merged `registry/` tree to GitHub Pages.

The published endpoint is:

- `https://<owner>.github.io/shuck-shells/index.json`

## Required secrets

The automation uses one GitHub App installation with these repository secrets:

- `SHUCK_SHELLS_APP_ID`
- `SHUCK_SHELLS_APP_INSTALLATION_ID`
- `SHUCK_SHELLS_APP_PRIVATE_KEY`

The workflows mint a short-lived installation token at runtime from those values. This setup intentionally does not require PR approvals on `main`. The nightly workflow opens or updates the refresh PR, and the validation workflow enables auto-merge after the required checks pass.

The app only needs repository access to `shuck-shells` with:

- `Contents: Read & write`
- `Pull requests: Read & write`
