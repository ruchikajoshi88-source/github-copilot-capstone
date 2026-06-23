param(
    [switch]$WithExternalDeps
)

$ErrorActionPreference = "Stop"

if ($WithExternalDeps) {
    docker compose -f infra/docker-compose.integration.yml up -d

    $env:RUN_EXTERNAL_INTEGRATION = "1"
    $env:POSTGRES_HOST = "localhost"
    $env:POSTGRES_PORT = "5432"
    $env:RABBITMQ_HOST = "localhost"
    $env:RABBITMQ_PORT = "5672"
}

python -m pytest tests/integration -m integration -q

if ($WithExternalDeps) {
    docker compose -f infra/docker-compose.integration.yml down
}
