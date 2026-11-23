"""Lectura del archivo `.env` y configuracion del autopiloto (sin dependencias externas).

El token nunca se imprime ni se registra: `Config.__repr__` lo enmascara y `redact()` lo borra de cualquier texto.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PLACEHOLDER = re.compile(r"pega|aqui|aquí|xxxx|tu_token|your", re.I)


def parse_env(text: str) -> dict:
    """KEY=VALUE por linea. Admite comentarios (#), `export`, comillas simples o dobles y comentarios tras el valor."""
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        if value[:1] in ("'", '"') and value.count(value[0]) >= 2:
            q = value[0]
            value = value[1:value.index(q, 1)]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        out[key] = value
    return out


def load_env(path: Path) -> dict:
    """Contenido de un .env (vacio si no existe)."""
    try:
        return parse_env(Path(path).read_text("utf-8-sig"))
    except OSError:
        return {}


def redact(text, *secrets) -> str:
    """Borra los secretos de un texto (para logs y mensajes de error)."""
    text = str(text)
    for s in secrets:
        if s and len(s) >= 6:
            text = text.replace(s, "***")
    return re.sub(r"(access_token=)[^&\s'\"]+", r"\1***", re.sub(r"(OAuth |Bearer )[\w\-.|]{12,}", r"\1***", text))


def _bool(value, default: bool) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("1", "true", "si", "sí", "yes", "on")


def parse_times(text, label: str = "HORARIOS") -> tuple:
    """"11:30, 17:00;21:15" -> (("11:30", "17:00", "21:15"), [errores]). Ordena, quita repetidas y acepta "9:30"."""
    times, errors = [], []
    for tok in re.split(r"[,;\s]+", str(text or "").strip()):
        if not tok:
            continue
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", tok)
        if m and int(m[1]) < 24 and int(m[2]) < 60:
            hhmm = f"{int(m[1]):02d}:{m[2]}"
            if hhmm not in times:
                times.append(hhmm)
        else:
            errors.append(f"{label}: {tok!r} no es una hora HH:MM de 24 horas (sepáralas con comas: 11:30,17:00).")
    return tuple(sorted(times)), errors


@dataclass(frozen=True)
class Config:
    page_id: str = ""
    token: str = field(default="", repr=False)
    version: str = "v26.0"
    photo_times: tuple = ("11:30",)   # franjas horarias de las imagenes (HORARIOS_FOTOS)
    video_times: tuple = ("18:00",)   # franjas horarias de los Reels (HORARIOS_VIDEOS)
    jitter_min: int = 1               # minutos
    jitter_max: int = 15
    max_photos: int = 1               # limite diario de imagenes (MAX_FOTOS_DIA), independiente del de videos
    max_videos: int = 1               # limite diario de Reels (MAX_VIDEOS_DIA)
    ai_label: bool = True             # marca los Reels como contenido generado/editado con IA (la voz es sintetica)
    dry_run: bool = False
    tolerance_hours: float = 3.0      # si el PC estuvo apagado/dormido mas que esto, esa tarea del dia se omite
    retries: int = 2                  # reintentos de PUBLICACION (no se vuelve a renderizar)
    retry_minutes: int = 20
    gen_timeout_min: int = 25
    image_out: Path = ROOT / "output_imagenes"
    video_out: Path = ROOT / "output"
    log_file: Path = ROOT / "autopiloto.log"
    state_file: Path = ROOT / "estado_autopiloto.json"
    parse_errors: tuple = ()          # valores del .env que no se pudieron interpretar (salen en problems())
    notes: tuple = ()                 # avisos (claves en desuso)

    def times(self, kind: str) -> tuple:
        return self.photo_times if kind == "foto" else self.video_times

    def limit(self, kind: str) -> int:
        """Publicaciones maximas por dia de ese tipo (0 = ese tipo esta desactivado)."""
        if not self.times(kind):
            return 0
        return self.max_photos if kind == "foto" else self.max_videos

    def __repr__(self) -> str:
        tok = f"{self.token[:3]}…({len(self.token)} caracteres)" if self.token else "(vacío)"
        return (f"Config(page_id={self.page_id!r}, token={tok}, version={self.version}, fotos={','.join(self.photo_times)} "
                f"(máx {self.max_photos}), videos={','.join(self.video_times)} (máx {self.max_videos}), "
                f"jitter={self.jitter_min}-{self.jitter_max} min, dry_run={self.dry_run})")

    @classmethod
    def from_sources(cls, file_env: Mapping | None = None, environ: Mapping | None = None, root: Path = ROOT) -> "Config":
        """`.env` + variables de entorno (estas ultimas mandan). Los valores invalidos se reportan en `problems()`."""
        env = {**(file_env or {}), **{k: v for k, v in (environ if environ is not None else os.environ).items()
                                      if k in ENV_KEYS}}

        errors, notes = [], []

        def num(key, default, cast=int):
            try:
                return cast(str(env.get(key, "")).strip().replace(",", ".")) if env.get(key, "") != "" else default
            except ValueError:
                return default

        def path(key, default: Path) -> Path:
            v = env.get(key, "").strip()
            return (Path(v) if Path(v).is_absolute() else root / v) if v else default

        def times(key, legacy, default):
            """HORARIOS_* (varias, separadas por comas). Vacio = ese tipo desactivado. FOTO_HORA/VIDEO_HORA siguen valiendo."""
            raw = env.get(key)
            if raw is None and env.get(legacy) is not None:
                notes.append(f"{legacy} está en desuso: usa {key} (admite varias horas separadas por comas).")
                raw = env.get(legacy)
            if raw is None:
                return default
            found, bad = parse_times(raw, key)
            errors.extend(bad)
            return found

        def limit(key, default):
            raw = str(env.get(key, "")).strip()
            if raw == "":
                return default
            if not re.fullmatch(r"\d+", raw):
                errors.append(f"{key}={raw!r} debe ser un número entero (0 desactiva ese tipo).")
                return default
            return int(raw)

        photo_times = times("HORARIOS_FOTOS", "FOTO_HORA", ("11:30",))
        video_times = times("HORARIOS_VIDEOS", "VIDEO_HORA", ("18:00",))
        if env.get("MAX_POSTS_DIA", "") != "":
            notes.append("MAX_POSTS_DIA ya no se usa: los límites son independientes (MAX_FOTOS_DIA y MAX_VIDEOS_DIA).")

        return cls(
            page_id=env.get("PAGE_ID", "").strip(), token=env.get("PAGE_ACCESS_TOKEN", "").strip(),
            version=env.get("GRAPH_VERSION", "v26.0").strip() or "v26.0",
            photo_times=photo_times, video_times=video_times,
            max_photos=limit("MAX_FOTOS_DIA", len(photo_times)), max_videos=limit("MAX_VIDEOS_DIA", len(video_times)),
            jitter_min=num("JITTER_MIN", 1), jitter_max=num("JITTER_MAX", 15),
            ai_label=_bool(env.get("IA_ETIQUETA"), True), dry_run=_bool(env.get("DRY_RUN"), False),
            tolerance_hours=num("TOLERANCIA_HORAS", 3.0, float), retries=num("REINTENTOS", 2),
            retry_minutes=num("REINTENTO_MIN", 20), gen_timeout_min=num("TIMEOUT_GENERAR_MIN", 25),
            image_out=path("SALIDA_IMAGENES", root / "output_imagenes"), video_out=path("SALIDA_VIDEOS", root / "output"),
            log_file=path("LOG_ARCHIVO", root / "autopiloto.log"),
            state_file=path("ESTADO_ARCHIVO", root / "estado_autopiloto.json"),
            parse_errors=tuple(errors), notes=tuple(notes),
        )

    def problems(self, need_credentials: bool = True) -> list:
        """Lista de errores de configuracion en español (vacia = todo bien)."""
        out = []
        if need_credentials:
            if not re.fullmatch(r"\d{5,}", self.page_id):
                out.append("PAGE_ID falta o no es numérico (copia el ID de tu página en .env).")
            if len(self.token) < 20 or PLACEHOLDER.search(self.token):
                out.append("PAGE_ACCESS_TOKEN falta o sigue siendo el texto de ejemplo (pon tu token de página en .env).")
        out.extend(self.parse_errors)
        if not (0 <= self.jitter_min <= self.jitter_max <= 120):
            out.append(f"JITTER_MIN/JITTER_MAX ({self.jitter_min}-{self.jitter_max}) deben cumplir 0 <= min <= max <= 120 minutos.")
        for name, value in (("MAX_FOTOS_DIA", self.max_photos), ("MAX_VIDEOS_DIA", self.max_videos)):
            if not (0 <= value <= 30):
                out.append(f"{name}={value} debe estar entre 0 y 30 (Meta limita los Reels publicados por API a 30 cada 24 h).")
        if not any(self.limit(k) for k in ("foto", "video")):
            out.append("No hay ninguna franja activa: pon horas en HORARIOS_FOTOS o HORARIOS_VIDEOS y un límite mayor que 0.")
        if not re.fullmatch(r"v\d+\.\d+", self.version):
            out.append(f"GRAPH_VERSION={self.version!r} no tiene el formato vNN.N (por ejemplo v26.0).")
        return out


ENV_KEYS = frozenset({
    "PAGE_ID", "PAGE_ACCESS_TOKEN", "GRAPH_VERSION", "HORARIOS_FOTOS", "HORARIOS_VIDEOS", "MAX_FOTOS_DIA", "MAX_VIDEOS_DIA",
    "FOTO_HORA", "VIDEO_HORA", "MAX_POSTS_DIA", "JITTER_MIN", "JITTER_MAX",
    "IA_ETIQUETA", "DRY_RUN", "TOLERANCIA_HORAS", "REINTENTOS", "REINTENTO_MIN", "TIMEOUT_GENERAR_MIN", "SALIDA_IMAGENES",
    "SALIDA_VIDEOS", "LOG_ARCHIVO", "ESTADO_ARCHIVO",
})
