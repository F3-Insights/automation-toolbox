#!/usr/bin/env bash
# detect-db-type.sh: Detect database type and connection method from project files.
# Outputs JSON to stdout. Run from any project root.

set -euo pipefail

db_type="unknown"
orm="unknown"
migration_tool="unknown"
migration_dir="unknown"
is_supabase=false
connection_env_var="unknown"

# --- Supabase Detection ---
if [[ -d "supabase" ]] || [[ -f "supabase/config.toml" ]]; then
  db_type="postgres"
  is_supabase=true
  migration_tool="supabase"
  migration_dir="supabase/migrations"
  connection_env_var="DATABASE_URL"
fi

# --- ORM / Migration Tool Detection ---

# Prisma
if [[ -f "prisma/schema.prisma" ]]; then
  orm="prisma"
  migration_tool="prisma"
  migration_dir="prisma/migrations"
  if grep -q "postgresql\|postgres" prisma/schema.prisma 2>/dev/null; then
    db_type="postgres"
  elif grep -q "mysql" prisma/schema.prisma 2>/dev/null; then
    db_type="mysql"
  elif grep -q "sqlite" prisma/schema.prisma 2>/dev/null; then
    db_type="sqlite"
  fi
  # Extract env var from datasource
  env_match=$(grep -oP 'env\("([^"]+)"\)' prisma/schema.prisma 2>/dev/null | head -1 | grep -oP '"[^"]+"' | tr -d '"')
  [[ -n "$env_match" ]] && connection_env_var="$env_match"
fi

# Drizzle
if [[ -f "drizzle.config.ts" ]] || [[ -f "drizzle.config.js" ]]; then
  orm="drizzle"
  migration_tool="drizzle"
  migration_dir="drizzle"
  [[ "$db_type" == "unknown" ]] && db_type="postgres"
fi

# SQLAlchemy / Alembic
if [[ -f "alembic.ini" ]] || [[ -d "alembic" ]]; then
  orm="sqlalchemy"
  migration_tool="alembic"
  migration_dir="alembic/versions"
  [[ "$db_type" == "unknown" ]] && db_type="postgres"
fi

# Django
if [[ -f "manage.py" ]]; then
  orm="django"
  migration_tool="django"
  migration_dir="*/migrations"
  [[ "$db_type" == "unknown" ]] && db_type="postgres"
fi

# TypeORM
if [[ -f "ormconfig.json" ]] || [[ -f "ormconfig.ts" ]] || [[ -f "ormconfig.js" ]]; then
  orm="typeorm"
  migration_tool="typeorm"
  migration_dir="src/migrations"
  [[ "$db_type" == "unknown" ]] && db_type="postgres"
fi

# --- Direct DB Detection from Dependencies ---
if [[ "$db_type" == "unknown" ]]; then
  if [[ -f "package.json" ]]; then
    if grep -q '"pg"\|"postgres"\|"@neondatabase"' package.json 2>/dev/null; then
      db_type="postgres"
    elif grep -q '"mysql2"\|"mysql"' package.json 2>/dev/null; then
      db_type="mysql"
    elif grep -q '"better-sqlite3"\|"sqlite3"' package.json 2>/dev/null; then
      db_type="sqlite"
    elif grep -q '"mongodb"\|"mongoose"' package.json 2>/dev/null; then
      db_type="mongodb"
    fi
  fi
  if [[ -f "requirements.txt" ]] || [[ -f "pyproject.toml" ]]; then
    if grep -qr "psycopg\|asyncpg" requirements.txt pyproject.toml 2>/dev/null; then
      db_type="postgres"
    elif grep -qr "pymysql\|mysqlclient" requirements.txt pyproject.toml 2>/dev/null; then
      db_type="mysql"
    elif grep -qr "pymongo\|motor" requirements.txt pyproject.toml 2>/dev/null; then
      db_type="mongodb"
    fi
  fi
fi

# --- Connection Env Var Detection ---
if [[ "$connection_env_var" == "unknown" ]]; then
  # Check .env.example for common DB env vars
  for env_file in .env.example .env.local.example .env.template; do
    if [[ -f "$env_file" ]]; then
      if grep -q "DATABASE_URL" "$env_file" 2>/dev/null; then
        connection_env_var="DATABASE_URL"
      elif grep -q "DB_URL" "$env_file" 2>/dev/null; then
        connection_env_var="DB_URL"
      elif grep -q "SUPABASE_DB_URL" "$env_file" 2>/dev/null; then
        connection_env_var="SUPABASE_DB_URL"
      elif grep -q "POSTGRES_URL" "$env_file" 2>/dev/null; then
        connection_env_var="POSTGRES_URL"
      fi
      break
    fi
  done
fi

# --- Docker Database Detection ---
if [[ -f "docker-compose.yml" ]] || [[ -f "docker-compose.yaml" ]]; then
  compose_file="docker-compose.yml"
  [[ -f "docker-compose.yaml" ]] && compose_file="docker-compose.yaml"
  if grep -q "postgres" "$compose_file" 2>/dev/null; then
    [[ "$db_type" == "unknown" ]] && db_type="postgres"
  elif grep -q "mysql\|mariadb" "$compose_file" 2>/dev/null; then
    [[ "$db_type" == "unknown" ]] && db_type="mysql"
  elif grep -q "mongo" "$compose_file" 2>/dev/null; then
    [[ "$db_type" == "unknown" ]] && db_type="mongodb"
  fi
fi

# Default connection env var for postgres
if [[ "$connection_env_var" == "unknown" ]] && [[ "$db_type" == "postgres" ]]; then
  connection_env_var="DATABASE_URL"
fi

# Output JSON
cat <<EOF
{
  "db_type": "${db_type}",
  "orm": "${orm}",
  "migration_tool": "${migration_tool}",
  "migration_dir": "${migration_dir}",
  "is_supabase": ${is_supabase},
  "connection_env_var": "${connection_env_var}"
}
EOF
