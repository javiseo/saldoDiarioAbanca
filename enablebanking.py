"""Cliente mínimo de la API de Enable Banking (https://api.enablebanking.com)."""
import base64, json, os, time

try:  # en PCs corporativos usa el almacén de certificados de Windows (opcional)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

API = "https://api.enablebanking.com"
APP_ID = os.environ["ENABLE_APP_ID"]


def _clave_privada():
    """Lee la clave del Secret (GitHub) o del fichero .pem (local)."""
    txt = os.getenv("ENABLE_PRIVATE_KEY")
    data = txt.replace("\\n", "\n").encode() if txt else \
        open(os.getenv("ENABLE_KEY_FILE", f"{APP_ID}.pem"), "rb").read()
    return serialization.load_pem_private_key(data, password=None)


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _jwt() -> str:
    """JWT RS256 firmado con la clave de la app (válido 1 hora)."""
    ahora = int(time.time())
    header = {"typ": "JWT", "alg": "RS256", "kid": APP_ID}
    payload = {"iss": "enablebanking.com", "aud": "api.enablebanking.com",
               "iat": ahora, "exp": ahora + 3600}
    msg = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}"
    firma = _clave_privada().sign(msg.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{msg}.{_b64url(firma)}"


def _req(metodo: str, path: str, **kw):
    h = {"Authorization": f"Bearer {_jwt()}", "Content-Type": "application/json"}
    r = requests.request(metodo, f"{API}{path}", headers=h, timeout=30, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{metodo} {path} -> {r.status_code}: {r.text[:500]}")
    return r.json()


def aplicacion():
    return _req("GET", "/application")


def bancos(pais: str):
    return _req("GET", "/aspsps", params={"country": pais})["aspsps"]


def iniciar_autorizacion(banco: str, pais: str, redirect_url: str, state: str, valid_until: str):
    return _req("POST", "/auth", json={
        "access": {"valid_until": valid_until},
        "aspsp": {"name": banco, "country": pais},
        "state": state,
        "redirect_url": redirect_url,
        "psu_type": "personal",
    })


def crear_sesion(code: str):
    return _req("POST", "/sessions", json={"code": code})


def sesion(session_id: str):
    return _req("GET", f"/sessions/{session_id}")


def detalles_cuenta(uid: str):
    return _req("GET", f"/accounts/{uid}/details")


def saldos(uid: str):
    return _req("GET", f"/accounts/{uid}/balances")["balances"]
