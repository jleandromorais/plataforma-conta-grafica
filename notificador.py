"""
notificador.py — Alertas por e-mail (Gmail SMTP gratuito)

Envia e-mail quando o pipeline termina (sucesso) ou falha.
Custo: R$ 0,00 — usa o Gmail que você já tem.

Configuração (uma vez só):
    1. Acesse myaccount.google.com → Segurança → Verificação em 2 etapas (ative)
    2. Ainda em Segurança → Senhas de app → crie uma senha para "GraphAccount"
    3. Coloque no config.env:
          EMAIL_REMETENTE=seu@gmail.com
          EMAIL_SENHA_APP=xxxx xxxx xxxx xxxx   (senha de app, não a senha normal)
          EMAIL_DESTINATARIO=analista@empresa.com
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

logger = logging.getLogger(__name__)


def _num_br(valor: float, casas: int = 2) -> str:
    """Formata número no padrão BR (milhar '.', decimal ','), ex: 1.234.567,8900."""
    return f"{(valor or 0):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _carregar_config_email() -> dict[str, str]:
    """Lê credenciais do config.env e variáveis de ambiente."""
    import os

    cfg: dict[str, str] = {}
    config_path = Path(__file__).parent / "config.env"
    if config_path.exists():
        for linha in config_path.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            cfg[chave.strip()] = valor.strip()

    # Variáveis de ambiente têm prioridade
    for chave in ("EMAIL_REMETENTE", "EMAIL_SENHA_APP", "EMAIL_DESTINATARIO", "EMAIL_SMTP_HOST", "EMAIL_SMTP_PORT"):
        if chave in os.environ:
            cfg[chave] = os.environ[chave]

    return cfg


def _enviar(assunto: str, corpo: str, anexo: str | None = None) -> bool:
    """
    Envia um e-mail via SMTP com corpo texto e anexo opcional.
    Retorna True se enviou, False se não estava configurado ou falhou.
    """
    cfg = _carregar_config_email()

    remetente  = cfg.get("EMAIL_REMETENTE", "").strip()
    senha      = cfg.get("EMAIL_SENHA_APP", "").strip()
    destino    = cfg.get("EMAIL_DESTINATARIO", remetente).strip()
    smtp_host  = cfg.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port  = int(cfg.get("EMAIL_SMTP_PORT", "587"))

    if not remetente or not senha:
        logger.debug("Notificador: EMAIL_REMETENTE ou EMAIL_SENHA_APP não configurados — pulando")
        return False

    try:
        if anexo and Path(anexo).exists():
            msg = MIMEMultipart()
            msg["From"]    = remetente
            msg["To"]      = destino
            msg["Subject"] = assunto
            msg.attach(MIMEText(corpo, "plain", "utf-8"))

            with open(anexo, "rb") as f:
                parte = MIMEBase("application", "octet-stream")
                parte.set_payload(f.read())
            encoders.encode_base64(parte)
            parte.add_header(
                "Content-Disposition",
                f'attachment; filename="{Path(anexo).name}"',
            )
            msg.attach(parte)
        else:
            msg = EmailMessage()
            msg["From"]    = remetente
            msg["To"]      = destino
            msg["Subject"] = assunto
            msg.set_content(corpo)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(remetente, senha)
            smtp.send_message(msg)

        logger.info("[Notificador] E-mail enviado para %s: %s", destino, assunto)
        return True

    except Exception:
        logger.exception("[Notificador] Falha ao enviar e-mail")
        return False


def enviar_sucesso(periodo: str, arquivo: str, resultados: dict, anexar_excel: bool = True) -> bool:
    """E-mail de sucesso ao final do pipeline, com o Excel gerado como anexo."""
    aud  = resultados.get("auditoria", {})
    ret  = resultados.get("ret", {})
    cgf  = resultados.get("cgf", {})
    rp   = resultados.get("concilia", {})
    pmpv = resultados.get("pmpv", {})
    scg  = resultados.get("scg", {})

    nome_arquivo = Path(arquivo).name if arquivo else "—"
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    corpo = f"""
✅ PIPELINE CONCLUÍDO COM SUCESSO
{'='*50}
Período   : {periodo}
Gerado em : {agora}
Arquivo   : {nome_arquivo}
{'='*50}

RESUMO DO FECHAMENTO
{'─'*50}
CGR (Auditoria XML)  : R$ {_num_br(aud.get('cgr', 0)):>16}   ({aud.get('n_itens', 0)} documentos)
RET (Encargos)       : R$ {_num_br(ret.get('ret', 0)):>16}   ({ret.get('n_itens', 0)} itens)
CGF (Volume Faturado):    {_num_br(cgf.get('volume_final', 0), 4):>16} m³
RP  (Penalidades)    : R$ {_num_br(rp.get('rp', 0)):>16}
PMPV                 : R$ {_num_br(pmpv.get('pmpv', 0), 4):>16} /m³
{'─'*50}
RPV  = CGR − CGF     : R$ {_num_br(scg.get('rpv', 0)):>16}
SCG  = RPV+RET+RP    : R$ {_num_br(scg.get('scg', 0)):>16}
{'='*50}

O relatório Excel foi gerado automaticamente.
Abra o arquivo para conferência ou use o app desktop se precisar corrigir algo.

-- GraphAccount Pro Pipeline
"""

    return _enviar(
        assunto=f"✅ Fechamento {periodo} gerado | GraphAccount Pro",
        corpo=corpo.strip(),
        anexo=arquivo if anexar_excel else None,
    )


def enviar_falha(etapas: str | list[str], periodo: str) -> bool:
    """E-mail de alerta quando uma ou mais etapas do pipeline falham.

    Aceita uma etapa única (str, ex: "consolidação") ou várias (list[str],
    quando múltiplos módulos independentes falharam na mesma execução).
    """
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    lista_etapas = [etapas] if isinstance(etapas, str) else list(etapas)
    plural = len(lista_etapas) > 1
    rotulo = ", ".join(e.upper() for e in lista_etapas)
    rotulo_campo = "Etapas que falharam" if plural else "Etapa que falhou "
    passo_processar = (
        f"3. Processe as etapas '{', '.join(lista_etapas)}' manualmente"
        if plural else
        f"3. Processe a etapa '{lista_etapas[0]}' manualmente"
    )

    corpo = f"""
⛔ PIPELINE FALHOU — AÇÃO NECESSÁRIA
{'='*50}
{rotulo_campo}: {rotulo}
Período      : {periodo}
Hora da falha: {agora}
{'='*50}

O que fazer:
  1. Verifique o log em: logs/app.log
  2. Abra o app desktop (GraphAccount Pro)
  {passo_processar}
  4. As demais etapas podem ser reprocessadas depois

O Excel final NÃO foi gerado — processamento interrompido
para evitar relatório com dados incompletos.
{'='*50}

-- GraphAccount Pro Pipeline
"""

    return _enviar(
        assunto=f"⛔ PIPELINE FALHOU [{rotulo}] | {periodo}",
        corpo=corpo.strip(),
    )


def testar_conexao() -> bool:
    """
    Testa se o e-mail está configurado corretamente.
    Use para verificar antes de agendar o pipeline:
        python notificador.py
    """
    return _enviar(
        assunto="✅ Teste de conexão — GraphAccount Pro",
        corpo=(
            "Este é um e-mail de teste do pipeline GraphAccount Pro.\n\n"
            "Se você recebeu esta mensagem, a configuração de e-mail está correta.\n\n"
            f"Enviado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        ),
    )


if __name__ == "__main__":
    print("Testando configuração de e-mail...")
    if testar_conexao():
        print("✅ E-mail enviado com sucesso! Configuração correta.")
    else:
        print("❌ Falha. Verifique EMAIL_REMETENTE e EMAIL_SENHA_APP no config.env")
        print("   Consulte COMO_USAR_AUTOMACAO.md para o passo a passo.")
