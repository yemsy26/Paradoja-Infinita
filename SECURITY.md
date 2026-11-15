# Política de seguridad

## Versiones con soporte

| Versión | Soporte |
|---|---|
| 1.x | Sí |

## Reportar una vulnerabilidad

**No abras un issue público** para vulnerabilidades. Usa el
[reporte privado de GitHub](https://github.com/yemsy26/Paradoja-Infinita/security/advisories/new)
(*Security → Report a vulnerability*) e incluye:

- Descripción del problema e impacto.
- Pasos para reproducirlo y versión afectada.
- Si es posible, una propuesta de corrección.

Responderemos lo antes posible y coordinaremos la divulgación una vez corregido el problema.

## Alcance y buenas prácticas

El programa se ejecuta en local y no expone servicios de red. Los puntos a tener en cuenta son:

- **Procesos externos:** invoca `ffmpeg` y `ffprobe` del `PATH` con argumentos en lista (sin shell). Instala FFmpeg
  desde una fuente de confianza.
- **Red:** solo `edge-tts` se conecta a Internet (síntesis de voz). El texto enviado es el guion generado por el
  programa; no se envían datos personales.
- **Archivos:** los videos se escriben únicamente dentro de la carpeta indicada con `--out` (por defecto `output/`); la caché de voz se guarda en `.cache/`.
- **`iniciar.bat`:** puede instalar Python y FFmpeg con `winget`. Revisa el script antes de ejecutarlo.
- No subas a este repositorio claves, tokens, rutas personales ni videos generados.
