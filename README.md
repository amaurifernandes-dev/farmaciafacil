# FarmáciaFácil

Sistema web de gestão e vendas para farmácias pequenas (SaaS).

- **Backend:** Python, FastAPI, SQLAlchemy 2, Alembic
- **Banco:** PostgreSQL (Neon em produção), multi-tenant com `farmacia_id` e Row Level Security
- **Frontend:** React (em breve)

## Rodando o backend localmente

Requisitos: Python 3.12+, [uv](https://docs.astral.sh/uv/) e Docker.

```bash
docker compose up -d            # Postgres 16 em localhost:5432
cd backend
cp .env.example .env            # ajuste JWT_SECRET
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.criar_farmacia --cnpj 12345678000190 \
    --razao "Farmácia Exemplo LTDA" --fantasia "Farmácia Exemplo" --uf SP \
    --admin-nome "Maria" --admin-email maria@exemplo.com
uv run uvicorn app.main:app --reload
```

A documentação interativa da API fica em http://localhost:8000/docs. Faça login em
`POST /api/v1/auth/login` e use o token no botão **Authorize**.

## Testes

```bash
cd backend
uv run pytest
```

Os testes usam o banco `farmaciafacil_test` (criado pelo `docker compose`) e recriam o schema a cada rodada.

## Usando o Neon

1. Crie um projeto no [Neon](https://neon.tech) e anote a connection string do usuário dono (`neondb_owner`).
2. Crie um segundo usuário para a aplicação, por exemplo `ff_app`, em **Roles** no painel.
   A aplicação precisa de um usuário que **não** seja dono das tabelas, senão o RLS não se aplica a ela.
3. No `.env`:
   - `MIGRATION_DATABASE_URL` = connection string do `neondb_owner`
   - `DATABASE_URL` = connection string do `ff_app` (pode usar o endpoint com `-pooler`)
   - `APP_DB_ROLE=ff_app`
4. Rode `uv run alembic upgrade head` e crie a primeira farmácia com o script acima.

## Como o isolamento entre farmácias funciona

- O token JWT carrega o `farmacia_id` do usuário.
- A cada transação, a aplicação executa `set_config('app.farmacia_id', ..., true)`.
- Toda tabela tem uma política de RLS que só libera linhas da farmácia da transação, para leitura e escrita.
- `farmacia_id` é preenchido pelo próprio banco a partir dessa configuração.
- O login usa a função `auth_buscar_usuario`, a única que lê usuários antes de a farmácia ser conhecida.

Os testes em `backend/tests/test_isolamento.py` garantem que uma farmácia não vê nem altera dados de outra.
