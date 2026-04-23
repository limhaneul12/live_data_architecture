# 04. Generation And Scaffolding

## Goal

Make new bounded-context creation fast, but keep the generated structure aligned with the real architecture rules.

## Generate Rule

Current supported command:

- `make generate <domain_name>`
- `make generate DOMAIN=<domain_name>`

## Generated Structure Rule

The scaffold shape is:

- `<backend_root>/<domain>/application/`
- `<backend_root>/<domain>/domain/`
- `<backend_root>/<domain>/domain/repositories/`
- `<backend_root>/<domain>/infrastructure/`
- `<backend_root>/<domain>/interface/`
- `<backend_root>/<domain>/interface/schemas/`
- `<backend_root>/<domain>/interface/router/`
- `<test_root>/<domain>/`
- `<backend_root>/<domain>/containers.py` as a minimal stub generation target

Application growth inside the scaffold should follow the same rule documented elsewhere:

- start simple under `application/`
- if use cases grow large, split toward `application/{feature}_usecase/`

## Repository Scaffold Rule

Repository contract folders generated for new domains should use plural `repositories/`:

- `<backend_root>/<domain>/domain/repositories/` for ABC contracts / ports
- `<backend_root>/<domain>/infrastructure/repositories/` for concrete persistence adapters when needed

Existing singular `repository/` folders are legacy and should not be copied into new collector work.

## Test Scaffold Rule

### Adopt now

When scaffolding a new domain, create `<test_root>/<domain>/` together with the code folders.

Reason:

- it reinforces `tests/<domain>` as the default test ownership pattern
- it prevents new domains from being added without any testing surface

Recommended generated substructure once test surface grows:

- `<test_root>/<domain>/builders/`
- `<test_root>/<domain>/factories/`
- `<test_root>/<domain>/conftest.py` when domain fixtures are needed

## Shared Code Rule For Generation

Do not generate `shared/` content from the domain scaffold.

Reason:

- `shared/` is not domain-owned
- broad generation of shared helpers encourages premature abstraction

## Container Rule For Generation

Generate a minimal `containers.py` stub because local domain composition is the default bounded-context extension point.

If a domain does not need it yet, keep it minimal.

## Validation Rule

Generated domain names should remain:

- snake_case
- lowercase-first
- filesystem-safe

## Change Coordination Note

If the scaffold shape changes, update all three together:

1. `Makefile`
2. pytest discovery config
3. structure rule docs
