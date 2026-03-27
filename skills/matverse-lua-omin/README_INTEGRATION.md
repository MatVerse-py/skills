# Integração no seu app Lua (OpenResty) – Zero-ENV + Híbrido (Lua + Sidecar)

Objetivo: **seu app Lua não carrega segredos persistidos**. Ele apenas:
1) valida requisições (nonce/exp/HMAC),
2) pede chaves efêmeras ao sidecar via **socket local**,
3) escreve eventos em **ledger append-only** (framing binário) e
4) emite **Evidence Receipt** verificável offline.

## Arquitetura (mínimo)

- **OpenResty (Lua)**: gateway + validação + emissão de receipt + append em ledger.
- **Sidecar AutoHeal (Python)**: rotação curta + detecção de exposição (quando configurada) + kill-switch.
- **Verificador Offline (Python)**: replay do ledger e verificação dos receipts.

## Zero-ENV (modelo)

- Nada de `.env` com segredos no app.
- OpenResty obtém material secreto **somente em runtime** via Unix socket:
  - `/run/matverse/autoheal.sock` (apenas local)

## Passo-a-passo

1) Suba o stack de referência:

```bash
cd skills/matverse-lua-omin
cp docker-compose.hybrid.yml docker-compose.yml
docker compose up -d
```

2) Teste health:

```bash
curl -s http://localhost:8080/health
curl -s http://localhost:8888/health
```

3) Teste endpoint assinado (exemplo):

```bash
python sidecar/tools/sign_request.py --url http://localhost:8080/api/v1/payment --json '{"amount":10,"recipient":"x"}'
```

4) Verifique offline:

```bash
python sidecar/verifier/offline_verify.py --ledger ./data/ledger.bin --receipt ./data/receipts/<id>.json
```

## Observações de produção

- A rotação real de tokens (Telegram/HF/etc.) depende de **APIs reais do provedor**. Este pacote deixa hooks (interfaces) para você plugar.
- Kill-switch é **fail-closed**: quando acionado, OpenResty retorna 503 e recusa pagamentos.
- Ledger é append-only com `fsync` no writer do sidecar (ou no host).
