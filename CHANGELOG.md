# Changelog

Todos los cambios relevantes se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [1.0.0] - 2026-11-15

Primera versión pública.

### Añadido
- Render procedural en GPU (OpenGL headless con moderngl) enviado por pipe a FFmpeg con NVENC (`h264_nvenc`,
  `hevc_nvenc`) y *fallback* a `libx264`. Salida 1080×1920, 60 fps, 63 s.
- 8 modos de video: reto de anomalía, ilusión óptica, bucle infinito, sincronización (pause game), test de visión
  (Ishihara), enjambre, ojo mágico (autoestereograma) y contraste simultáneo; más modo 100 % aleatorio.
- Diversificación por semilla: 5 paletas, 7 figuras, layouts, movimientos, velocidades, estructura temporal, tipo de
  ilusión y de bucle.
- Voz neuronal con `edge-tts` y subtítulos ASS sincronizados por palabra; audio procedural sin derechos de autor.
- Menú interactivo y CLI (`--mode`, `--count`, `--seed`, `--duration`, `--voice`, `--codec`, `--out`, `--keep-work`).
- Salida organizada por fecha y por video, con archivo `.txt` de metadata (título, descripción, hashtags, respuestas).
- `iniciar.bat`: instalación automática de Python, dependencias y FFmpeg en Windows.
- Pruebas automatizadas, integración continua, documentación y plantillas de GitHub.
