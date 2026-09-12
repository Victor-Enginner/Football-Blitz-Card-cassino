# Deploy 24/7 — VPS Hetzner (sandbox em nuvem)

> **Arquitetura honesta:** o **observer** (MutationObserver no DOM do jogo) roda
> no **seu PC** — precisa do login manual do cassino + IP brasileiro. A **nuvem**
> (VPS) roda o Command Center, os agentes IA e o Telegram 24/7, recebendo os
> eventos do seu PC via WebSocket autenticado.

```
SEU PC (browser + login cassino)          VPS Hetzner 24/7
┌─────────────────────────────┐          ┌──────────────────────────────┐
│ fb_observer.js              │   WSS    │ Caddy (TLS) → Command Center │
│ MutationObserver (read-only)│ ───────► │  ledger + travas + game      │
└─────────────────────────────┘          │  Hermes agent (combo IA)     │
                                         │  OmniRoute → AIsa (fallback) │
      você acessa o dashboard ──────────►│  Telegram bot                │
      https://dashboard.seudominio.com   └──────────────────────────────┘
```

## 1. Criar o VPS

| Opção | Spec | Preço | Observação |
|---|---|---|---|
| **Hetzner CX22** (recomendado) | 2 vCPU / 4GB / 40GB | ~€3.79/mês | roda toda a stack |
| Hetzner CAX11 (ARM) | 2 vCPU / 4GB | ~€3.79/mês | same price, ARM images |
| Fly.io (PaaS) | shared 1x / 256MB+ | ~$2-5/mês | mais mão-na-roda p/ multi-container |

Regiões: **Ashburn, VA (US East)** tem a melhor latência Brasil→EUA (~120-150ms).
Falkenstein/Dilas (DE) fica ~200-250ms. Dashboard não é tempo-real crítico;
o observer empurra por WS — 150ms é imperceptível.

1. Conta em console.hetzner.cloud → New Project → **Add Server**
2. Location: `Ashburn` · Image: `Ubuntu 24.04` · Type: `CX22`
3. SSH key (cole sua pubkey) → Create

## 2. Preparar o servidor

```bash
ssh root@SEU_IP
apt update && apt -y upgrade
curl -fsSL https://get.docker.com | sh     # Docker + compose plugin

# firewall: só SSH, HTTP, HTTPS
ufw allow OpenSSH && ufw allow 80 && ufw allow 443
ufw --force enable
```

## 3. Subir a stack

```bash
mkdir -p /opt/fbcc && cd /opt/fbcc
# copie a pasta command-center (git clone, scp ou rsync)
git clone SEU_REPO server && cd server

cd deploy
cat > .env <<'EOF'
OBSERVER_TOKEN=troque-por-um-token-longo-aleatorio
TELEGRAM_TOKEN=seu_token_do_botfather
TELEGRAM_CHAT_ID=seu_chat_id
AISA_API_KEY=sk-aisa-...
EOF
chmod 600 .env

docker compose up -d
docker compose logs -f command-center   # deve mostrar "Uvicorn running"
```

Sem domínio? Use Cloudflare Tunnel em vez do Caddy:
```bash
docker run -d --name tunnel --restart unless-stopped --network deploy_default \
  cloudflare/cloudflared:latest tunnel --no-autoupdate run \
  --token SEU_CLOUDFLARE_TOKEN
```

## 4. Conectar o observer (seu PC)

1. Abra o jogo no Chrome, faça login, F12 → Console
2. Cole o conteúdo de `observer/fb_observer.js` + ENTER
3. Conecte:
```js
const obs = fbObserverCreate({
  server: "wss://dashboard.seudominio.com/ws",   // ou ws://SEU_IP:8765/ws (s/ TLS)
  token:  "troque-por-um-token-longo-aleatorio", // mesmo do .env do VPS
});
// status: obs.status()   |   parar: obs.disconnect()
```

> **Importante:** o observer é **read-only**. Ele nunca clica, nunca aposta.
> Toda ação continua sendo humana e registrada no ledger.

## 5. Validar

```bash
curl https://dashboard.seudominio.com/api/health
# {"status":"ok","chain_integrity":{...}}
```
- Dashboard: registre um evento manual → deve aparecer no Telegram
- Telegram: `/status`, `/saldo`, `/apostas`, `/relatorio`, `/parar`
- Banco de dados no volume `fb-data` → backup: `docker run --rm -v fb-data:/data -v $PWD:/b alpine tar czf /b/fbcc-backup.tgz /data`

## 6. Atualizar

```bash
cd /opt/fbcc/server && git pull
docker compose build command-center && docker compose up -d command-center
```

## Custos mensais estimados

| Item | Custo |
|---|---|
| Hetzner CX22 | ~€3.79 (~R$23) |
| Domínio (opcional, Cloudflare) | ~$10/ano |
| OmniRoute (combo free) | R$0 (providers free-tier) |
| AIsa fallback | pay-per-use (~$0.001-0.01/análise) |
| **Total** | **~R$25-35/mês** |
