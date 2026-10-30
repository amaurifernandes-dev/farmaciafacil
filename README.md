# FarmáciaFácil

Sistema web de gestão e vendas para farmácias pequenas (SaaS).

- **Backend:** Python, FastAPI, SQLAlchemy 2, Alembic
- **Banco:** PostgreSQL (Neon em produção), multi-tenant com `farmacia_id` e Row Level Security
- **Frontend:** React + Vite + TypeScript

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

## Rodando o frontend

Com o backend rodando na porta 8000:

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

O Vite repassa as chamadas `/api` para o backend. Telas:

- **/**: visão geral com vendas do dia, gráfico da semana, acesso rápido e avisos.
- **/vendas**: pré-vendas aguardando o caixa, últimas vendas (cancelamento pelo gerente) e **/vendas/pre-venda** para montar um pedido no balcão.
- **/pdv**: frente de caixa em tela cheia, operada pelo teclado e pelo leitor de código de barras.
- **/caixas**: este computador, caixas abertos, PDVs cadastrados e últimos fechamentos.
- **/estoque**: alertas, saldo de cada loja, entrada manual e transferência entre lojas.
- **/compras**: importação do XML da NF-e de compra (conferência e entrada no estoque) e sugestão de compras.
- **/financeiro**: contas a pagar e a receber, fiado e fluxo de caixa.
- **/clientes**: cadastro com aniversariantes do mês e clientes que não voltam, e a ficha de cada cliente
  (total comprado, o que leva sempre, últimas compras, pontos e fiado).
- **/faltas**: faltas e encomendas. O balcão (ou o caixa, com F1) anota o que o cliente pediu e não tinha;
  com nome ou telefone vira encomenda, e quando o produto entra no estoque ela aparece em "Chegaram" com o
  botão para avisar no WhatsApp. A venda para o cliente da encomenda dá baixa nela sozinha.
- **/promocoes**: % de desconto, preço especial ou leve e pague, por período e loja; o PDV aplica sozinho
  (vale a de maior desconto) e cada promoção mostra quanto vendeu.
- **/relatorios**: vendas do período (com lucro bruto e comparação com o período anterior), lucro por
  produto com curva ABC e produtos parados no estoque; as tabelas baixam como planilha.
- **/configuracoes**: fornecedores, produtos, usuários, minha farmácia (matriz e filiais) e configurações gerais.

Cada lote pertence a uma loja. A venda baixa do estoque da loja do PDV, a entrada escolhe a loja
(ou vai para a matriz) e a transferência leva o lote para outra loja com o mesmo número e validade.
Na nota pelo XML, o fornecedor é cadastrado pelo CNPJ, a loja é a do CNPJ de destino e cada item é
reconhecido pelo código que o fornecedor já usou antes ou pelo código de barras. A nota só entra no
estoque depois de conferida e confirmada.

Na sugestão de compras, o que faltou no balcão conta como venda e as encomendas que estão esperando entram
por cima do estoque normal.

Programa de pontos (ligado em Configurações gerais): o cliente identificado no PDV (F8) ganha pontos
por real gasto e troca por desconto numa próxima compra (F9). Os pontos podem expirar depois de alguns
meses sem compras, e cancelar a venda desfaz os pontos dela.

## Caixas: monocaixa, multicaixa e PDVs registrados

Cada loja escolhe, em Configurações gerais:

- **Monocaixa**: qualquer computador faz pré-venda; só o PDV central da loja abre caixa, recebe e emite a NFC-e.
- **Multicaixa**: cada PDV ativo da loja abre o próprio caixa e recebe direto.

Um computador vira PDV quando um gerente clica em **Registrar este computador** na tela Caixas. A API gera uma
chave secreta, o navegador guarda e manda no cabeçalho `X-Terminal` em toda chamada. Não usamos o IP porque o
servidor está na internet: todos os computadores da loja chegariam com o IP do roteador, que ainda muda quando a
conexão cai. Registrar outro computador no mesmo PDV revoga a chave do anterior.

Perfis: administrador, gerente, farmacêutico, operador de caixa, atendente (só pré-venda) e estoque.

### Atalhos do PDV

| Tecla | Ação |
| --- | --- |
| Enter | Adiciona o código bipado/digitado (`3*789...` para 3 unidades). Texto sem número busca por nome |
| F1 | Anotar falta: o item sem estoque, o produto não encontrado ou o que digitar (com cliente, vira encomenda) |
| F2 | Buscar produto por nome (setas + Enter) |
| F3 | Alterar a quantidade do item selecionado |
| F4 | Pagamento (Alt+1 dinheiro, Alt+2 débito, Alt+3 crédito, Alt+4 pix; Enter vazio finaliza) |
| F6 | Desconto na venda |
| F7 | Receber uma pré-venda pelo número |
| F8 / F9 | Identificar o cliente / usar os pontos dele |
| ↑ ↓ / Del | Selecionar / remover item |
| Esc | Voltar; na venda, Esc duas vezes cancela |
| F10 | Fechar caixa |

A venda em andamento fica salva no navegador até ser finalizada.

## NFC-e

A emissão passa pela [Focus NFe](https://focusnfe.com.br), que assina o XML e fala com a SEFAZ.
O certificado A1, o CSC (token do QR Code), a inscrição estadual e o endereço da farmácia são
cadastrados no painel da Focus, não no nosso banco.

1. No `.env`, `NFCE_PROVEDOR=focus` e os tokens `FOCUS_NFE_TOKEN_HOMOLOGACAO` / `FOCUS_NFE_TOKEN_PRODUCAO`.
   Para desenvolver sem a Focus, use `NFCE_PROVEDOR=falso`: autoriza tudo em memória.
2. Um gerente salva a configuração fiscal em `PUT /api/v1/fiscal/configuracao` (ambiente, CFOP e
   CSOSN/CST padrão). Começa em homologação.
3. Todo produto vendido precisa de NCM. CFOP, CSOSN/CST e PIS/COFINS do produto, se preenchidos,
   valem no lugar do padrão (ex.: medicamento com ICMS-ST: CFOP 5405, CSOSN 500).

Ao finalizar a venda a NFC-e é emitida na mesma chamada e volta em `venda.nota`. A venda é gravada
mesmo se a nota falhar; nesse caso `POST /api/v1/vendas/{id}/nfce` reenvia (a referência é o id da
venda, então não duplica) e `GET /api/v1/vendas/{id}/nfce?atualizar=true` consulta uma nota que ficou
em processamento. Cancelar a venda cancela a NFC-e antes; a SEFAZ exige motivo com 15 caracteres ou
mais e, em geral, até 30 minutos após a emissão. Se ela recusar, a venda não é cancelada.

## Testes

```bash
cd backend && uv run pytest     # backend
cd frontend && npm test         # regras do carrinho do PDV
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
