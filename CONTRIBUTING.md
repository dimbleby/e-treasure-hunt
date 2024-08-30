# Setting up a development environment

1. Install Python 3.12
2. Install uv - see [the uv docs](https://docs.astral.sh/uv/#getting-started)
3. Run `uv sync --extra azure` to install the project's dependencies

# Running the CI lints locally

See [linting.yml](.github/workflows/linting.yml) for the list of linting
commands run by the CI on Github, such as:

```shell
$ uv run ruff check .
$ uv run ruff format --check .
$ uv run mypy .
```
