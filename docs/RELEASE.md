# Releasing FrameDiet to PyPI

Package: `framediet` (version from `pyproject.toml`). Checked 2026-11-08: the name `framediet` (and `frame-diet`) is free on PyPI and TestPyPI.

Nothing here uploads by itself. You run the upload commands yourself.

## One-time setup

1. Create accounts (you do this in the browser):
   - https://pypi.org/account/register/
   - optionally https://test.pypi.org/account/register/ for a dry run
2. Enable two-factor authentication on each account (PyPI requires 2FA for uploads).
3. Create an API token:
   - First upload of a new project: create an **account-wide** token (the project does not exist yet, so a project-scoped token cannot be made).
   - After the first upload: create a token **scoped to the `framediet` project** and use only that one.
4. Store the token in a password manager. Never commit it or paste it into a file in the repo.

## Build and check (locally)

From `D:\dev\FrameDiet`, in a clean virtualenv:

```bash
python -m venv .venv-release
.venv-release/Scripts/pip install build twine
.venv-release/Scripts/python -m build --outdir dist
.venv-release/Scripts/twine check dist/*
```

`twine check` must print `PASSED` for both the `.whl` and the `.tar.gz`.
Delete `dist/` and `build/` after uploading if you do not need them (both are in `.gitignore`).

## Upload

Optional dry run on TestPyPI:

```bash
.venv-release/Scripts/twine upload --repository testpypi dist/*
```

Then install from TestPyPI in a fresh venv to check it works (`pip install -i https://test.pypi.org/simple/ framediet`).

Real upload:

```bash
.venv-release/Scripts/twine upload dist/*
```

When asked for credentials, use username `__token__` and paste the API token as the password. The token input is hidden.

## Important

- **A version number can never be uploaded again**, even after deleting the release on PyPI. If something is wrong, bump the version in `pyproject.toml` (for example `0.1.1`), rebuild, and upload again.
- Build the artifacts from a clean commit so the sdist matches the repo.
- Check the project page on PyPI after upload: the README renders, and the Homepage, Repository and Issues links work.

## Recommended later: Trusted Publishing (no tokens)

Instead of API tokens, PyPI can trust a GitHub Actions workflow directly:

1. On PyPI, open the project (after the first upload) → Publishing → add a GitHub publisher with owner `AIsoidet`, repository `FrameDiet`, workflow file name (for example `release.yml`), and environment (optional, for example `pypi`).
2. Add a workflow that runs on a published GitHub release, uses `pypa/gh-action-pypi-publish` with `id-token: write` permission, and does not need any secret.

This workflow file is not added yet. Write it when you want it.
