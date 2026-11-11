"""Consulta el saldo de tus cuentas vía Enable Banking y lo envía por Telegram."""
import json, os, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()
import requests
import enablebanking as eb

TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHAT_ID"]
SESSION_ID = os.environ["ENABLE_SESSION_ID"]
DEBUG = "--debug" in sys.argv
AVISO_DIAS = 7
# Preferencia de tipo de saldo (ISO 20022): disponible > contable
PREFERENCIA = ["ITAV", "CLAV", "XPCD", "ITBD", "CLBD", "OPAV", "OPBD"]


def telegram(txt: str):
    r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                      json={"chat_id": TG_CHAT, "text": txt, "parse_mode": "HTML"},
                      timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Telegram -> {r.status_code}: {r.text}")


def euros(x):
    try:
        return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(x)


def elegir_saldo(lista):
    if not lista:
        return None
    por_tipo = {b.get("balance_type"): b for b in lista}
    return next((por_tipo[t] for t in PREFERENCIA if t in por_tipo), lista[0])


def main():
    s = eb.sesion(SESSION_ID)
    if DEBUG:
        print("Sesión:", json.dumps({k: s.get(k) for k in ("status", "access")}, indent=2))
    ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    lineas = [f"🏦 <b>Saldo</b> – {ahora:%d/%m/%Y %H:%M}"]

    for uid in s.get("accounts", []):
        try:
            d = eb.detalles_cuenta(uid)
        except Exception:
            d = {}
        nombre = d.get("name") or d.get("product") or "Cuenta"
        iban = (d.get("account_id") or {}).get("iban") or ""
        lista = eb.saldos(uid)
        if DEBUG:
            print(json.dumps(lista, indent=2, ensure_ascii=False))
        b = elegir_saldo(lista)
        if b:
            imp = b["balance_amount"]
            lineas.append(f"• {nombre} ···{iban[-4:]}: <b>{euros(imp['amount'])} {imp['currency']}</b>")
        else:
            lineas.append(f"• {nombre} ···{iban[-4:]}: sin datos de saldo")

    hasta = (s.get("access") or {}).get("valid_until")
    if hasta:
        dias = (datetime.fromisoformat(hasta.replace("Z", "+00:00")) - datetime.now(timezone.utc)).days
        if dias <= AVISO_DIAS:
            lineas.append(f"\n⚠️ El permiso caduca en {dias} días: ejecuta autorizar.py y actualiza ENABLE_SESSION_ID.")

    if DEBUG:
        print("\n".join(lineas)); return
    telegram("\n".join(lineas))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        if not DEBUG:
            try:
                telegram("⚠️ Error consultando el saldo. Revisa el log de la ejecución "
                         "(si el permiso caducó, ejecuta autorizar.py).")
            except Exception as te:
                print(f"ERROR TELEGRAM: {te}")
        sys.exit(1)
