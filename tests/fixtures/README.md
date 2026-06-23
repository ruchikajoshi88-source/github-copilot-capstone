# Integration Fixtures

- `integration_payloads.py`: canonical merge event and header builders.

External dependency checks are optional and controlled by environment variables:
- `RUN_EXTERNAL_INTEGRATION=1`
- `POSTGRES_HOST` / `POSTGRES_PORT`
- `RABBITMQ_HOST` / `RABBITMQ_PORT`

To run with local Docker dependencies:
- `./scripts/run-integration.ps1 -WithExternalDeps`
