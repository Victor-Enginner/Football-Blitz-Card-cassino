# -*- coding: utf-8 -*-
"""Gera RELATORIO_PROJETO.pdf — tudo feito + validação 100%."""
from fpdf import FPDF
from fpdf.enums import XPos, YPos

def _mc(pdf, h, t):
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, h, t, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

def tx(s):
    return (s.replace("×", "x").replace("→", "->").replace("χ²", "chi2")
             .replace("✅", "[OK]").replace("❌", "[X]").replace("⚠", "[!]")
             .replace("🟡", "(M)").replace("🔵", "(V)").replace("🟢", "(E)")
             .replace("🔊", "").replace("–", "-").replace("—", "-")
             .replace("“", '"').replace("”", '"').replace("’", "'"))

class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120)
        self.cell(0, 6, "Football Blitz Command Center - Relatorio do Projeto (PAPER)", align="R")
        self.ln(10)
    def h1(self, t):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(20)
        _mc(self, 8, tx(t))
        self.ln(2)
    def h2(self, t):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40)
        _mc(self, 7, tx(t))
        self.ln(1)
    def p(self, t):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30)
        _mc(self, 6, tx(t))
        self.ln(1)
    def item(self, t):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30)
        _mc(self, 6, tx("  - " + t))

def build(path="RELATORIO_PROJETO.pdf"):
    pdf = PDF()
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()
    pdf.h1("Football Blitz Command Center - Relatorio Completo")
    pdf.p("Data: 12/09/2026 - Backend v2.1.0-real-system - 63 testes verdes - Modo PAPER (sem aposta real). Observer somente-leitura do jogo Pragmatic Football Blitz na Zona de Jogo.")
    pdf.h2("1. O que foi construido")
    for t in [
        "Backend FastAPI :8766 com ledger append-only + hash-chain (events/audit/decisions), policy engine (200/dia, stop-loss, cooldown, kill-switch), paper bets 1:1 e 11:1.",
        "Regra anti-sequencia: 4x MANDANTE -> VISITANTE R$ 0,50 e vice-versa; empate quebra. Sinal visual + popup + sirene; confirmacao em 1 clique.",
        "Escada PAPER [0.50, 1, 2, 4, 6, 12]: perda avanca, win/push reseta, esgotamento volta ao inicio + pausa. Exposicao maxima R$ 25,50. PENDENTE: confirmar 6 ou 8 no nivel 5.",
        "AUTO-PAPER (default OFF): 1 paper automatico por streak fresco, com sem-aposta-aberta, limite 200/dia, loss-streak 8 e rotacao de sessao. Auditoria em audit_log.",
        "Matematica real (risk.py): frequencia, Wilson CI, entropia Shannon, streaks, autocorrelacao, chi2, EV, drawdown, ruina, Kelly (estudo), walk-forward. Martingale = educacional.",
        "Frontend app 6 abas (SINAL/MESA/PAPEL/RISCO/BRAIN/MAIS): orbes, grade 100, gauges, lados quentes, holograma scan de cartas no canto, grafo de 7 agentes reais, por-que, notacoes deduplicadas, paleta Ctrl+K, tour, simples/especialista, PWA.",
        "Sons: sirene de entrada, confirmação, GREEN + moeda, buzz de loss; mudo global.",
        "Observer fb_observer.js (MutationObserver, cartas H/A) -> ws local com token -> ledger. Backend nunca toca rede externa do jogo.",
        "Travas aplicadas: ARENA BET_MODE REAL->SIMULACAO; fallback OpenClaw llama->laguna; OpenCode 1.18.30 reparado; OBSERVER_TOKEN ativo; TEST_MODE sem segredos no bundle.",
    ]:
        pdf.item(t)
    pdf.h2("2. Evidencias de funcionamento")
    for t in [
        "GET /api/health = ok, chain True/True/True. GET /ready = true PAPER.",
        "63 testes pytest verdes (ledger, policy, game, risk, progression, sinais, agentes, simulação).",
        "Banca paper ~R$ 235 (inicio 200) em apostas de teste; 4x->oposto validado em teste e ao vivo.",
        "Compressao local medida 11% (README 4932->4391). 9Router: disponivel, compressao NAO comprovada.",
        "Chat OpenRouter primario OK ~740ms; 445 modelos; llama-3.3 ausente -> laguna.",
        "Auditoria de segredos limpa: sem JSESSIONID/cookies/cookies em codigo; .env ignorados no git.",
    ]:
        pdf.item(t)
    pdf.h2("3. Erros vistos (e causa real)")
    for t in [
        "Timeouts no restart: boot uvicorn leva 15-25s (RAG + Telegram). Aguardar, nao e bug.",
        "WS 403 sem token: correto apos hardening (token obrigatorio).",
        "node --check falhou 1x: faltava ')' em L.push (corrigido).",
        "pytest so roda com workdir=command-center (sombra do modulo stdlib 'compression').",
        "Porta 8766 em uso apos restart rapido: aguardar liberacao do socket.",
    ]:
        pdf.item(t)
    pdf.h2("4. Para validar 100% (amanha)")
    for t in [
        "P0: backup DBs+.env; FB_MAX_EVENTS_PER_DAY 200->3000; confirmar escada (6 ou 8); backend na 8766 + /ready.",
        "P1: rodada supervisionada 4-6h (INICIAR -> login -> fbObserverCreate -> AUTO-PAPER + sons) + collect_200.py --target 200.",
        "P2: chi-square, hit-rate 4x vs baseline, walk-forward 1-100/101-200; veredito escrito sem meio-termo.",
        "P3: servico Windows + watchdog, Telegram critico, teste de queda (kill -> restart -> chain True?).",
        "Criterio 100%: ledger integro + 200 giros reais + 6h sem erro + servico + Telegram. Sem aposta real.",
    ]:
        pdf.item(t)
    pdf.h2("5. Riscos e limites honestos")
    pdf.p("EV da mesa e negativo (house edge). Nenhum gatilho cria vantagem sem vies fisico comprovado. ContextFilter bloqueia ~40% das janelas aleatorias (sensivel demais). Transicoes carta-a-carta em 2000 giros = ruido (chi2 29.5 < 51). WebSocket Pragmatic direto nao existe p/ usuarios (só B2B). i-have-adhd nao aprende mercado (só estilo de resposta).")
    out = path
    pdf.output(out)
    print("PDF_OK", out)
    return out


if __name__ == "__main__":
    build()
