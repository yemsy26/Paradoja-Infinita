# Guía de contribución

¡Gracias por tu interés en Paradoja Infinita! Las contribuciones son bienvenidas: correcciones, nuevos modos de video,
paletas, idiomas y mejoras de documentación.

## Antes de empezar

- Busca en los [issues](https://github.com/yemsy26/Paradoja-Infinita/issues) si ya existe lo que quieres proponer.
- Para cambios grandes (un modo nuevo, cambios en el pipeline), abre primero un issue para acordar el enfoque.
- Lee la [arquitectura](docs/ARQUITECTURA.md); explica cómo está organizado el código y cómo añadir un tipo de reto.
- Para añadir acertijos basta con editar `content/acertijos.json` (formato `{"q": "...", "a": "..."}`).

## Entorno de desarrollo

```powershell
git clone https://github.com/yemsy26/Paradoja-Infinita.git
cd Paradoja-Infinita
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest
```

Para generar videos también necesitas FFmpeg en el `PATH` (ver [README](README.md#requisitos)).

## Flujo de trabajo

1. Haz un *fork* y crea una rama descriptiva: `feat/modo-xyz`, `fix/subtitulos-solapados`, `docs/instalacion`.
2. Haz commits pequeños y atómicos siguiendo [Conventional Commits](https://www.conventionalcommits.org/es/):
   `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `perf:`, `chore:`.
3. Asegúrate de que `python -m pytest` pasa y de que el cambio visual se ha comprobado generando un video real.
4. Abre un *pull request* usando la plantilla y enlaza el issue relacionado.

## Criterios de código

- Python 3.10+, tipado razonable y funciones cortas. Comentarios solo cuando explican el *porqué*.
- **Determinismo:** misma semilla y modo deben generar el mismo video. Si cambias el orden de las llamadas a
  `random` en `scene.build_scene`, avísalo en el PR: cambia los videos de semillas existentes.
- **Shaders:** mantén la convención `px.y` hacia abajo y deja el objetivo del reto fuera de `SUB_BAND`.
- **Texto en pantalla:** no dibujes texto en GLSL; usa subtítulos ASS.
- **Sin datos personales:** no incluyas rutas locales, correos, claves ni material con derechos de autor.
- Añade o actualiza pruebas en `tests/` cuando cambies lógica.
- Actualiza `README.md`, `README.en.md` y `CHANGELOG.md` si el cambio es visible para el usuario.

## Reporte de errores

Usa la plantilla de *bug report* e incluye: versión de Python, sistema operativo, GPU, versión de FFmpeg
(`ffmpeg -version`), el comando ejecutado, la semilla y el log (el programa guarda `ffmpeg.log` con `--keep-work`).

## Licencia

Al contribuir aceptas que tu aportación se distribuya bajo la licencia [MIT](LICENSE) del proyecto.
