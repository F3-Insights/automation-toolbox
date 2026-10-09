#!/usr/bin/env bash
# detect_project_type.sh: describe a software project in one JSON object.
#
# Reads the project's marker files (package.json, pyproject.toml, Cargo.toml, go.mod and
# the like) and prints its language, framework, package manager, test runner, start and
# test commands, and whether it has Docker or CI configuration. Reads only; writes nothing.
#
# Input:  an optional project directory; with none it inspects the current directory.
# Output: one JSON object on stdout. Exit 1 when the argument is not a directory.
#
# Example: bash detect_project_type.sh path/to/repo

set -euo pipefail

if [[ $# -gt 0 ]]; then
  if [[ ! -d "$1" ]]; then
    echo "detect_project_type.sh: not a directory: $1" >&2
    exit 1
  fi
  cd "$1"
fi

language="unknown"
framework="unknown"
package_manager="unknown"
test_runner="unknown"
start_command="unknown"
test_command="unknown"
has_docker=false
has_ci=false

# Docker detection
[[ -f "Dockerfile" || -f "docker-compose.yml" || -f "docker-compose.yaml" ]] && has_docker=true

# CI detection
[[ -d ".github/workflows" || -f ".gitlab-ci.yml" || -f "Jenkinsfile" || -f ".circleci/config.yml" || -f ".travis.yml" ]] && has_ci=true

# --- Node.js / JavaScript / TypeScript ---
if [[ -f "package.json" ]]; then
  language="javascript"
  [[ -f "tsconfig.json" ]] && language="typescript"

  # Package manager
  if [[ -f "bun.lockb" || -f "bun.lock" ]]; then
    package_manager="bun"
  elif [[ -f "pnpm-lock.yaml" ]]; then
    package_manager="pnpm"
  elif [[ -f "yarn.lock" ]]; then
    package_manager="yarn"
  else
    package_manager="npm"
  fi

  # Framework detection from package.json
  if grep -q '"next"' package.json 2>/dev/null; then
    framework="nextjs"
    start_command="${package_manager} run dev"
  elif grep -q '"nuxt"' package.json 2>/dev/null; then
    framework="nuxt"
    start_command="${package_manager} run dev"
  elif grep -q '"@angular/core"' package.json 2>/dev/null; then
    framework="angular"
    start_command="${package_manager} run start"
  elif grep -q '"react"' package.json 2>/dev/null; then
    framework="react"
    start_command="${package_manager} run start"
  elif grep -q '"vue"' package.json 2>/dev/null; then
    framework="vue"
    start_command="${package_manager} run serve"
  elif grep -q '"express"' package.json 2>/dev/null; then
    framework="express"
    start_command="${package_manager} run start"
  elif grep -q '"fastify"' package.json 2>/dev/null; then
    framework="fastify"
    start_command="${package_manager} run start"
  elif grep -q '"hono"' package.json 2>/dev/null; then
    framework="hono"
    start_command="${package_manager} run start"
  fi

  # Test runner detection
  if grep -q '"vitest"' package.json 2>/dev/null; then
    test_runner="vitest"
    test_command="${package_manager} run test"
  elif grep -q '"jest"' package.json 2>/dev/null; then
    test_runner="jest"
    test_command="${package_manager} test"
  elif grep -q '"mocha"' package.json 2>/dev/null; then
    test_runner="mocha"
    test_command="${package_manager} test"
  elif grep -q '"playwright"' package.json 2>/dev/null; then
    test_runner="playwright"
    test_command="${package_manager} run test"
  elif grep -q '"cypress"' package.json 2>/dev/null; then
    test_runner="cypress"
    test_command="${package_manager} run test"
  fi

  # Fallback start/test from scripts
  if [[ "$start_command" == "unknown" ]]; then
    if grep -q '"start"' package.json 2>/dev/null; then
      start_command="${package_manager} run start"
    elif grep -q '"dev"' package.json 2>/dev/null; then
      start_command="${package_manager} run dev"
    fi
  fi
  if [[ "$test_command" == "unknown" ]]; then
    if grep -q '"test"' package.json 2>/dev/null; then
      test_command="${package_manager} test"
    fi
  fi

# --- Python ---
elif [[ -f "pyproject.toml" || -f "setup.py" || -f "setup.cfg" || -f "requirements.txt" ]]; then
  language="python"

  # Package manager
  if [[ -f "pyproject.toml" ]] && grep -q '\[tool\.poetry\]' pyproject.toml 2>/dev/null; then
    package_manager="poetry"
  elif [[ -f "Pipfile" ]]; then
    package_manager="pipenv"
  elif [[ -f "pyproject.toml" ]] && grep -q 'hatchling\|hatch' pyproject.toml 2>/dev/null; then
    package_manager="hatch"
  elif command -v uv &>/dev/null && [[ -f "uv.lock" ]]; then
    package_manager="uv"
  else
    package_manager="pip"
  fi

  # Framework
  if [[ -f "manage.py" ]] || grep -qr "django" requirements.txt pyproject.toml 2>/dev/null; then
    framework="django"
    start_command="python manage.py runserver"
  elif grep -qr "fastapi\|FastAPI" requirements.txt pyproject.toml 2>/dev/null; then
    framework="fastapi"
    start_command="uvicorn main:app --reload"
  elif grep -qr "flask\|Flask" requirements.txt pyproject.toml 2>/dev/null; then
    framework="flask"
    start_command="flask run"
  fi

  # Test runner
  if [[ -f "pyproject.toml" ]] && grep -q '\[tool\.pytest' pyproject.toml 2>/dev/null; then
    test_runner="pytest"
    test_command="pytest"
  elif [[ -f "pytest.ini" || -f "conftest.py" ]]; then
    test_runner="pytest"
    test_command="pytest"
  elif [[ -f "tox.ini" ]]; then
    test_runner="tox"
    test_command="tox"
  else
    test_runner="pytest"
    test_command="pytest"
  fi

# --- Rust ---
elif [[ -f "Cargo.toml" ]]; then
  language="rust"
  package_manager="cargo"
  test_runner="cargo"
  test_command="cargo test"
  start_command="cargo run"

  if grep -q "actix-web\|actix_web" Cargo.toml 2>/dev/null; then
    framework="actix-web"
  elif grep -q "axum" Cargo.toml 2>/dev/null; then
    framework="axum"
  elif grep -q "rocket" Cargo.toml 2>/dev/null; then
    framework="rocket"
  fi

# --- Go ---
elif [[ -f "go.mod" ]]; then
  language="go"
  package_manager="go"
  test_runner="go"
  test_command="go test ./..."
  start_command="go run ."

  if grep -q "gin-gonic/gin" go.mod 2>/dev/null; then
    framework="gin"
  elif grep -q "labstack/echo" go.mod 2>/dev/null; then
    framework="echo"
  elif grep -q "gofiber/fiber" go.mod 2>/dev/null; then
    framework="fiber"
  fi

# --- Ruby ---
elif [[ -f "Gemfile" ]]; then
  language="ruby"
  package_manager="bundler"

  if [[ -f "config/routes.rb" ]]; then
    framework="rails"
    start_command="bundle exec rails server"
    test_command="bundle exec rails test"
    test_runner="minitest"
  elif grep -q "sinatra" Gemfile 2>/dev/null; then
    framework="sinatra"
    start_command="bundle exec ruby app.rb"
  fi

  if grep -q "rspec" Gemfile 2>/dev/null; then
    test_runner="rspec"
    test_command="bundle exec rspec"
  fi

# --- Java / Kotlin ---
elif [[ -f "pom.xml" ]]; then
  language="java"
  package_manager="maven"
  test_runner="maven"
  test_command="mvn test"
  start_command="mvn spring-boot:run"
  [[ -f "build.gradle.kts" ]] && language="kotlin"

elif [[ -f "build.gradle" || -f "build.gradle.kts" ]]; then
  language="java"
  [[ -f "build.gradle.kts" ]] && language="kotlin"
  package_manager="gradle"
  test_runner="gradle"
  test_command="./gradlew test"
  start_command="./gradlew bootRun"

# --- C# / .NET ---
elif compgen -G "*.csproj" >/dev/null || compgen -G "*.sln" >/dev/null; then
  language="csharp"
  package_manager="dotnet"
  test_runner="dotnet"
  test_command="dotnet test"
  start_command="dotnet run"

# --- Elixir ---
elif [[ -f "mix.exs" ]]; then
  language="elixir"
  package_manager="mix"
  test_runner="mix"
  test_command="mix test"
  start_command="mix phx.server"

  if grep -q "phoenix" mix.exs 2>/dev/null; then
    framework="phoenix"
  fi

# --- Makefile fallback ---
elif [[ -f "Makefile" ]]; then
  if grep -q '^test:' Makefile 2>/dev/null; then
    test_command="make test"
    test_runner="make"
  fi
  if grep -q '^run:\|^start:\|^dev:' Makefile 2>/dev/null; then
    start_command="make run"
  fi
fi

# Output JSON
cat <<EOF
{
  "language": "${language}",
  "framework": "${framework}",
  "package_manager": "${package_manager}",
  "test_runner": "${test_runner}",
  "start_command": "${start_command}",
  "test_command": "${test_command}",
  "has_docker": ${has_docker},
  "has_ci": ${has_ci}
}
EOF
