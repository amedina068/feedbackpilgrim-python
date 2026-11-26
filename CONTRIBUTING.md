# Contributing

Thank you for your help. This file tells you how to set up the project, run the checks and send a change.

## Set up the project

1. Install [uv](https://docs.astral.sh/uv/).
2. Clone the repository.
3. Install the dependencies:

   ```bash
   uv sync
   ```

## Run the checks

Run all four checks before you send a change. CI runs the same checks on Python 3.10 to 3.14.

```bash
uv run pytest              # tests
uv run ruff check .        # lint
uv run ruff format --check .
uv run mypy                # type check, strict mode
```

To run the tests on one Python version:

```bash
uv run --python 3.10 pytest
```

## Test vectors

`tests/fixtures/` has the test vectors of the identity hash and of the webhook signature. The script `gen-vectors.php` makes them from the code of the app. Do not change a vector by hand. If the app changes, make the vectors again and copy them here.

## Integration tests

The integration tests call a live Feedback Pilgrim instance. They run only when these two variables are set. Otherwise pytest skips them.

```bash
FEEDBACKPILGRIM_TEST_URL=https://feedback.example.com \
FEEDBACKPILGRIM_TEST_TOKEN=... \
uv run pytest -m integration
```

The integration tests are read-only. They list posts and tags.

> **CAUTION:** Do not put a token in a file of the repository. Do not paste a token in an issue or a pull request.

## Rules for code

- Write code in the style of `requests`: a small, obvious API with good defaults, PEP 8, full type hints, and dataclasses for the responses.
- Add a unit test with the fake transport of `tests/conftest.py` for each change of behavior.
- Do not add a dependency if the standard library can do the job.
- Do not add telemetry.

## Rules for text

Write docs, comments, error messages and commit messages in Simple English (ASD-STE100):

- Write short sentences. Use 20 words maximum in an instruction and 25 words maximum in a description.
- Use the active voice. Use the imperative for an instruction.
- Use one word for one meaning.
- Do not use contractions or semicolons.

## Send a change

1. Make a branch from `main`.
2. Make the change and run the checks.
3. Add a line to `CHANGELOG.md` under `Unreleased`.
4. Open a pull request. Fill in the template.

## Pull request titles

The title of each pull request must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). The `pr-title` check fails when the title does not follow it.

Use one of these types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore` or `revert`. The scope in parentheses is optional. Examples:

- `feat: add the testimonials resource`
- `fix: retry a request after a 429 response`
- `docs: add a webhook example to the README`

GitHub makes the release notes from the titles of the merged pull requests. A clear title gives a clear release note.

## Release

The `Release` workflow (`.github/workflows/release.yml`) builds the package and publishes it to PyPI with trusted publishing (OIDC). The `build` job runs the checks and builds the sdist and the wheel. The `publish` job runs in the `pypi` environment and gets a short-lived token from PyPI. The repository has no PyPI secret. The `pypi` environment accepts only the `main` branch and the `v*` tags.

1. Set the new version in `src/feedbackpilgrim/_version.py`.
2. In `CHANGELOG.md`, move the lines under `Unreleased` to a new section `## [<version>] - <date>`.
3. Open a pull request with these changes. Merge it.
4. Start the workflow: `gh workflow run release.yml --ref main`.
5. Create the GitHub release `v<version>`. Use the section of `CHANGELOG.md` as the notes.

### First release

PyPI creates the project at the first publish. Before the first release, add a pending publisher at <https://pypi.org/manage/account/publishing/>: project `feedbackpilgrim`, owner `amedina068`, repository `feedbackpilgrim-python`, workflow `release.yml`, environment `pypi`.

## Triage

Each new issue gets the `needs-triage` label. The maintainer reads the issue, adds a type label (for example `bug`, `enhancement` or `question`) and removes `needs-triage`.
