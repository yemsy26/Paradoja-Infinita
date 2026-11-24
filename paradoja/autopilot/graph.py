"""Cliente minimo de la Graph API de Meta para publicar en TU pagina: fotos (feed) y Reels.

Segun la guia oficial de Reels (https://developers.facebook.com/docs/video-api/guides/reels-publishing):
  1. POST  graph.facebook.com/{v}/{page}/video_reels   upload_phase=start   -> video_id, upload_url
  2. POST  rupload.facebook.com/video-upload/{v}/{video_id}  cabeceras Authorization: OAuth, offset, file_size
     (un solo cuerpo binario; si se corta, se reanuda desde `bytes_transfered` con la cabecera `offset`)
  3. POST  graph.facebook.com/{v}/{page}/video_reels   upload_phase=finish, video_state=PUBLISHED, description
Las fotos van por POST /{page}/photos (multipart: `source`; texto en `caption`).

Se necesita un token de PAGINA con pages_show_list, pages_read_engagement y pages_manage_posts. El cliente recibe un
objeto `http` con la API de `requests` (inyectable para pruebas), nunca imprime el token y distingue los fallos en
«seguro reintentar» y «ambiguo» (se pudo publicar pero no sabemos): en ese caso NO se reintenta para no duplicar.
"""
from __future__ import annotations

import mimetypes
import time
from pathlib import Path

from .envfile import redact

GRAPH = "https://graph.facebook.com"
# limite de llamadas / peticiones: se puede reintentar mas tarde
RATE_CODES = {4, 17, 32, 341, 613, 80001, 80002, 80003, 80004, 80005, 80006, 80008, 80009}
SOFT_CODES = {1, 2}                      # error temporal del servidor
FATAL_HINT = {
    190: "El token es inválido o caducó: genera un token de página nuevo y ponlo en PAGE_ACCESS_TOKEN.",
    200: "Faltan permisos (pages_manage_posts, pages_read_engagement y pages_show_list) o el usuario no puede crear contenido.",
    10: "Permiso no concedido a la app.",
    368: "Meta marcó la acción como abusiva o no permitida (revisa la página en Meta Business Suite y baja el ritmo).",
    324: "La imagen es inválida o no se pudo leer.",
    1363040: "Relación de aspecto no admitida (debe ser entre 16:9 y 9:16).",
    1363127: "Resolución no admitida (mínimo 540x960; recomendado 1080x1920).",
    1363128: "Duración no admitida (de 3 a 90 s).",
    1363129: "Fotogramas por segundo no admitidos (de 24 a 60).",
}


class GraphError(Exception):
    """Fallo de la API o de la red. `retry`: hay esperanza de que funcione mas tarde. `ambiguous`: la peticion pudo
    haber llegado a Meta (no reintentar a ciegas)."""

    def __init__(self, message, *, phase="", status=None, code=None, subcode=None, retry=False, ambiguous=False):
        super().__init__(message)
        self.phase, self.status, self.code, self.subcode = phase, status, code, subcode
        self.retry, self.ambiguous = retry, ambiguous

    def __str__(self) -> str:
        bits = [f"[{self.phase}]" if self.phase else "", super().__str__()]
        if self.code is not None:
            bits.append(f"(código {self.code}{f'/{self.subcode}' if self.subcode else ''})")
        return " ".join(b for b in bits if b)


def _never_sent(exc: Exception) -> bool:
    """True si la excepcion indica que la peticion ni siquiera salio (no hay riesgo de duplicado)."""
    names = " ".join(c.__name__ for c in type(exc).__mro__)
    text = str(exc).lower()
    return ("ConnectTimeout" in names or "NameResolutionError" in names or "failed to establish a new connection" in text
            or "getaddrinfo failed" in text or "name or service not known" in text)


def _strip_paging(obj):
    """Copia de `obj` sin ninguna clave `paging` (a cualquier profundidad)."""
    if isinstance(obj, dict):
        return {k: _strip_paging(v) for k, v in obj.items() if k != "paging"}
    if isinstance(obj, list):
        return [_strip_paging(v) for v in obj]
    return obj


class GraphClient:
    def __init__(self, page_id: str, token: str, version: str = "v26.0", http=None, sleep=time.sleep, log=None):
        self.page_id, self.token, self.version = page_id, token, version
        self._http, self.sleep, self.log = http, sleep, log
        self.base = f"{GRAPH}/{version}"

    # ------------------------------------------------------------------ utilidades
    @property
    def http(self):
        if self._http is None:
            import requests                       # perezoso: las pruebas inyectan un http falso
            self._http = requests
        return self._http

    def _say(self, msg: str) -> None:
        if self.log:
            self.log.info(redact(msg, self.token))

    def _error(self, resp, phase: str, ambiguous_if_unknown: bool = False) -> GraphError:
        """GraphError a partir de una respuesta HTTP con error."""
        status = getattr(resp, "status_code", None)
        try:
            err = (resp.json() or {}).get("error") or {}
        except Exception:
            err = {}
        code, sub = err.get("code"), err.get("error_subcode")
        msg = err.get("message") or str(getattr(resp, "text", ""))[:300] or f"HTTP {status}"
        low = f"{err.get('type', '')} {msg}".lower()
        retry = bool(err.get("is_transient")) or code in RATE_CODES or code in SOFT_CODES or (status or 0) >= 500 \
            or "offsetinvalid" in low or "partialrequest" in low or "processingfailed" in low
        hint = FATAL_HINT.get(code) or FATAL_HINT.get(sub)
        return GraphError(redact(f"{msg}{' — ' + hint if hint else ''}", self.token), phase=phase, status=status,
                          code=code, subcode=sub, retry=retry and not hint,
                          ambiguous=ambiguous_if_unknown and (status or 0) >= 500)

    def _call(self, method: str, url: str, phase: str, *, idempotent: bool = True, **kw) -> dict:
        """Una llamada HTTP. Lanza GraphError con la clasificacion adecuada."""
        try:
            resp = self.http.request(method, url, **kw)
        except Exception as e:                     # red caida, tiempo agotado...
            safe = _never_sent(e)
            raise GraphError(redact(f"{type(e).__name__}: {e}", self.token), phase=phase, retry=True,
                             ambiguous=(not idempotent and not safe)) from None
        status = getattr(resp, "status_code", 200)
        try:
            body = resp.json()
        except Exception:
            body = {}
        if status >= 400 or (isinstance(body, dict) and body.get("error")):
            raise self._error(resp, phase, ambiguous_if_unknown=not idempotent)
        return body if isinstance(body, dict) else {}

    # ------------------------------------------------------------------ comprobacion
    def check(self) -> dict:
        """Comprueba el token y el acceso a la pagina (no publica nada). -> {'id', 'name'}"""
        return self._call("GET", f"{self.base}/{self.page_id}", "check",
                          params={"fields": "id,name", "access_token": self.token}, timeout=30)

    # ------------------------------------------------------------------ lectura generica
    def get(self, path: str, **params) -> dict:
        """GET de solo lectura a cualquier nodo (`{id}`, `{pagina}/video_reels`, `` + `ids=a,b` para varios a la vez).
        Elimina todos los `paging` de la respuesta: sus URLs incluyen el token y nunca deben llegar a pantalla ni a un log."""
        params["access_token"] = self.token
        body = self._call("GET", f"{self.base}/{path.lstrip('/')}", "lectura", params=params, timeout=40)
        return _strip_paging(body)

    # ------------------------------------------------------------------ fotos
    def post_photo(self, path: Path, caption: str, alt: str | None = None) -> dict:
        """Publica una foto en el feed de la pagina. -> {'id': ..., 'post_id': ...}. Una sola peticion: si el resultado es
        ambiguo no se reintenta."""
        path = Path(path)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"

        def attempt(with_alt: bool) -> dict:
            data = {"caption": caption, "published": "true", "access_token": self.token}
            if with_alt and alt:
                data["alt_text_custom"] = alt[:900]
            with path.open("rb") as fh:
                return self._call("POST", f"{self.base}/{self.page_id}/photos", "foto", idempotent=False, data=data,
                                  files={"source": (path.name, fh, mime)}, timeout=(15, 300))

        try:
            out = attempt(True)
        except GraphError as e:                    # `alt_text_custom` sin confirmar para fotos publicadas: se prueba sin el
            if alt and e.code == 100 and "alt_text" in str(e).lower() and not e.ambiguous:
                self._say("La API no aceptó alt_text_custom: se publica sin texto alternativo.")
                out = attempt(False)
            else:
                raise
        return {"id": out.get("id"), "post_id": out.get("post_id") or out.get("id")}

    # ------------------------------------------------------------------ Reels
    def reel_status(self, video_id: str) -> dict:
        return (self._call("GET", f"{self.base}/{video_id}", "estado",
                           params={"fields": "status", "access_token": self.token}, timeout=30)).get("status") or {}

    def _uploaded_bytes(self, video_id: str, size: int) -> int:
        """Bytes que Meta ya recibio (para reanudar). 0 si no se puede saber."""
        try:
            up = self.reel_status(video_id).get("uploading_phase") or {}
            if str(up.get("status", "")).lower() in ("complete", "completed"):
                return size
            return max(0, min(size, int(up.get("bytes_transfered") or 0)))
        except Exception:
            return 0

    def _upload(self, upload_url: str, video_id: str, path: Path, attempts: int = 4) -> None:
        """Sube el archivo en un solo cuerpo binario; si se corta, consulta `bytes_transfered` y reanuda con `offset`."""
        size, offset = path.stat().st_size, 0
        for n in range(1, attempts + 1):
            headers = {"Authorization": f"OAuth {self.token}", "offset": str(offset), "file_size": str(size),
                       "Content-Type": "application/octet-stream"}
            self._say(f"Subiendo {path.name} ({size / 1e6:.1f} MB) desde el byte {offset} (intento {n}/{attempts})...")
            try:
                with path.open("rb") as fh:
                    fh.seek(offset)
                    body = self._call("POST", upload_url, "subida", headers=headers, data=fh, timeout=(15, 1800))
                if body.get("success") is False:
                    raise GraphError("Meta respondió sin éxito a la subida.", phase="subida", retry=True)
                return
            except GraphError as e:
                if not e.retry or n == attempts:
                    raise
                offset = self._uploaded_bytes(video_id, size)
                self._say(f"Subida interrumpida ({e}); se reanuda desde el byte {offset}.")
                self.sleep(min(60, 5 * n))

    def wait_reel(self, video_id: str, timeout: int = 900, interval: int = 10) -> dict:
        """Espera a que Meta procese y publique el Reel. -> resumen del estado (con 'timeout': True si se agoto el tiempo)."""
        waited, last = 0, {}
        while waited <= timeout:
            last = self.reel_status(video_id)
            vs = str(last.get("video_status", "")).lower()
            proc, pub = last.get("processing_phase") or {}, last.get("publishing_phase") or {}
            states = {str(proc.get("status", "")).lower(), str(pub.get("status", "")).lower()}
            if vs in ("error", "upload_failed", "expired") or "error" in states or pub.get("error") or proc.get("error"):
                detail = pub.get("error") or proc.get("error") or last.get("uploading_phase", {}).get("errors") or vs
                raise GraphError(redact(f"Meta no pudo procesar/publicar el Reel: {detail}", self.token), phase="proceso")
            pub_done = not pub or str(pub.get("status", "")).lower() in ("complete", "completed")
            if str(pub.get("publish_status", "")).lower() == "published" or (vs == "ready" and pub_done):
                return {"video_status": vs, "publish_status": "published", "timeout": False}
            self.sleep(interval)
            waited += interval
        return {"video_status": str(last.get("video_status", "")), "publish_status": "unknown", "timeout": True}

    def post_reel(self, path: Path, description: str, *, title: str | None = None, ai_generated: bool = False,
                  wait: bool = True) -> dict:
        """Publica un Reel (inicializacion, subida con reanudacion y finalizacion). -> {'video_id', 'status'}."""
        path = Path(path)
        start = self._call("POST", f"{self.base}/{self.page_id}/video_reels", "inicio",
                           data={"upload_phase": "start", "access_token": self.token}, timeout=60)
        video_id = start.get("video_id")
        if not video_id:
            raise GraphError("Meta no devolvió video_id al iniciar el Reel.", phase="inicio")
        url = start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{self.version}/{video_id}"
        self._upload(url, video_id, path)
        data = {"upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED", "description": description,
                "access_token": self.token}
        if ai_generated:                                  # sin etiqueta de IA el parametro NO se envia (ni como «false»)
            data["is_ai_generated"] = "true"
        if title:
            data["title"] = title
        done = self._call("POST", f"{self.base}/{self.page_id}/video_reels", "finalizar", idempotent=False, data=data,
                          timeout=(15, 120))
        if not done.get("success", True):
            raise GraphError("Meta respondió sin éxito al finalizar el Reel.", phase="finalizar")
        status = self.wait_reel(video_id) if wait else {"publish_status": "pending", "timeout": False}
        return {"video_id": video_id, "status": status}
