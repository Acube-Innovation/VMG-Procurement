# VMG Procurement

Custom procurement system for VMG on ERPNext v15: the normal purchase cycle is
rebuilt as custom, non-stock DocTypes (no Stock Ledger Entries, no Bins), while
fixed asset procurement runs on the core ERPNext purchase chain. See
[CLAUDE.md](CLAUDE.md) for the full business context, architecture and build plan.

All DocTypes, workflows, roles, print formats and custom fields live in the
single module **VMG Procurement**.

## Installation

From the bench directory:

```bash
cd $PATH_TO_YOUR_BENCH

# from a git remote:
bench get-app $URL_OF_THIS_REPO --branch develop
# (on this bench the app already exists under apps/vmg_procurement)

bench --site <site> install-app vmg_procurement
```

On this bench the site is `vmg`:

```bash
bench --site vmg install-app vmg_procurement
```

## Running migrations

After pulling changes or finishing a build step:

```bash
bench --site vmg migrate
```

This syncs DocType schemas and installs/updates all fixtures shipped by the app.
If desk assets changed, also run `bench build --app vmg_procurement` and
`bench --site vmg clear-cache`.

## Exporting fixtures

Customisations made through the UI (Custom Fields, Property Setters, Client and
Server Scripts, Print Formats, Roles, Workflows) must be exported into the app
so they are version controlled and portable:

```bash
bench --site vmg export-fixtures
```

The export is scoped by the `fixtures` list in
[vmg_procurement/hooks.py](vmg_procurement/hooks.py) to records belonging to the
VMG Procurement module (or named `VMG *`), and writes JSON files to
`vmg_procurement/fixtures/`. Commit those files together with the code change
that introduced them. On the next `bench --site <site> migrate` the fixtures are
re-imported, which is how the customisations reach other sites.

## Contributing

This app uses `pre-commit` (ruff, eslint, prettier, pyupgrade):

```bash
cd apps/vmg_procurement
pre-commit install
```

## License

MIT
