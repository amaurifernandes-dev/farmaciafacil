# FarmáciaFácil na farmácia (On-premise)

Esta pasta instala o FarmáciaFácil num computador da própria farmácia, o **computador servidor**.
Os caixas, o balcão e os celulares da loja usam o sistema por esse computador, pela rede da loja,
mesmo quando a internet cai. A internet só é usada para a NFC-e e para o assistente de IA.

Nesta versão não há loja online nem Pix pelo site. Os pedidos do WhatsApp e do telefone
continuam na tela Pedidos.

## O que precisa

- Um computador que fique ligado durante o expediente, com IP fixo na rede da loja
  (peça ao técnico da rede para fixar, por exemplo `192.168.0.10`).
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado nele (Windows ou Linux).
- Um HD externo ou uma pasta sincronizada com a nuvem para as cópias de segurança.

## Instalar (uma vez)

1. Copie esta pasta (`instalacao-farmacia`, junto com as pastas `backend` e `frontend` do projeto)
   para o computador servidor.
2. Copie `.env.exemplo` para `.env` e preencha: o `ENDERECO` (o IP do servidor), uma `SENHA_BANCO`
   longa, o `JWT_SECRET` e a `PASTA_COPIAS`.
3. Abra o terminal nesta pasta e ligue tudo:

   ```bash
   docker compose up -d --build
   ```

4. Cadastre a farmácia e o administrador (pede a senha do administrador):

   ```bash
   docker compose run --rm servidor python -m app.scripts.criar_farmacia --cnpj 12345678000190 \
       --razao "Farmácia Exemplo LTDA" --fantasia "Farmácia Exemplo" --uf SP \
       --admin-nome "Maria" --admin-email maria@exemplo.com
   ```

   O sistema aceita uma farmácia só. As filiais são cadastradas depois, em Minha farmácia.

## Em cada computador e celular da loja (uma vez)

O sistema usa `https`, porque o navegador só libera o caixa sem internet, a câmera e o login
guardado em página segura. O certificado é da própria farmácia, então cada aparelho precisa
confiar nele uma vez:

1. Abra `http://<ENDERECO>/certificado.crt` (exemplo: `http://192.168.0.10/certificado.crt`) e baixe o arquivo.
2. **Windows:** clique duas vezes no arquivo › Instalar certificado › Máquina local ›
   "Colocar todos os certificados no repositório a seguir" › **Autoridades de Certificação Raiz Confiáveis**.
   **Android:** Configurações › Segurança › Criptografia e credenciais › Instalar certificado › Certificado de CA.
3. Feche e abra o navegador e entre em `https://<ENDERECO>`. Salve nos favoritos.

## Cópia de segurança

O sistema faz uma cópia do banco ao ligar e depois uma por dia, na `PASTA_COPIAS`, e guarda os
últimos 30 dias. Confira de vez em quando se aparecem arquivos novos `farmaciafacil-AAAA-MM-DD.dump`.

Para voltar uma cópia (apaga os dados atuais e põe os da cópia):

```bash
docker compose stop servidor
docker compose exec -T banco pg_restore -U ff_owner -d farmaciafacil --clean --if-exists < copias/farmaciafacil-AAAA-MM-DD.dump
docker compose start servidor
```

## Atualizar

Com a versão nova do projeto na pasta, rode `docker compose up -d --build`. O banco se ajusta
sozinho ao ligar. Faça isso fora do expediente.
