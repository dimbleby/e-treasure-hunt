# Setting up a development environment

1. Install Python 3.12
2. Install poetry - see [the poetry docs](https://python-poetry.org/docs/)
3. Run `poetry install --extras azure` to install the project's dependencies

# Running the CI lints locally

See [linting.yml](.github/workflows/linting.yml) for the list of linting
commands run by the CI on Github, such as:

```shell
$ poetry run ruff check .
$ poetry run ruff format --check .
$ poetry run mypy .
```
