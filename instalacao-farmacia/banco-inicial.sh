#!/bin/sh
# Roda só na primeira vez que o banco é criado: cria o usuário que a aplicação usa.
# Ele não é dono das tabelas, então as regras de acesso (RLS) valem para ele.
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "CREATE ROLE ff_app LOGIN PASSWORD '$APP_DB_SENHA'"
