# Publishing

The [PyPI publishing workflow](.github/workflows/publish-pypi.yml) defines how
to publish this python package to PyPI. Every commit is deployed to
test.pypi.org, but in order to publish a new version to the production
pypi.org, you must edit [pyproject.toml](pyproject.toml) to bump the version
number, then run the following: (using version 9.9.9 for the sake of example)

```console
$ git tag v9.9.9
$ git push origin v9.9.9
```

# Trusted Publisher

As of this writing the "Trusted Publisher" on PyPI is defined under the
account `reynoldsnlp`, which is controlled by Rob Reynolds, Professor at
Brigham Young University.
