# Paradoja Infinita

[![CI](https://github.com/yemsy26/Paradoja-Infinita/actions/workflows/ci.yml/badge.svg)](https://github.com/yemsy26/Paradoja-Infinita/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Plataforma](https://img.shields.io/badge/probado%20en-Windows%2011-lightgrey.svg)

**Generador procedural de videos verticales cortos** (1080×1920, 60 fps, 63 s) basado en shaders GLSL, voz neuronal
y codificación por hardware NVENC. Pensado para canales de retos visuales, ilusiones ópticas y bucles geométricos
en formatos como Facebook Reels / In-Stream.

Cada ejecución parte de una **semilla** (`seed`) que decide paleta, figuras, estructura temporal, tipo de reto,
guion narrado y audio, de modo que cada video es estructuralmente distinto y a la vez **reproducible**.

> Idioma: Español · [English](README.en.md)

---

## Contenido

- [Características](#características)
- [Modos de video](#modos-de-video)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Uso](#uso)
- [Salida generada](#salida-generada)
- [Qué cambia con la semilla](#qué-cambia-con-la-semilla)
- [Rendimiento y GPU](#rendimiento-y-gpu)
- [Solución de problemas](#solución-de-problemas)
- [Desarrollo y pruebas](#desarrollo-y-pruebas)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Aviso legal](#aviso-legal)
- [Licencia](#licencia)

## Características

- **Render 100 % en GPU** (OpenGL headless con [moderngl](https://github.com/moderngl/moderngl)): los frames se calculan
  en un fragment shader y se envían por pipe a FFmpeg, sin escribir imágenes en disco.
- **Codificación NVENC** (`h264_nvenc` / `hevc_nvenc`) con *fallback* automático a `libx264`.
- **Voz neuronal gratuita** con [edge-tts](https://github.com/rany2/edge-tts), con tiempos por palabra para sincronizar
  subtítulos grandes, centrados y con la palabra activa resaltada.
- **Audio procedural** (drone + efectos) generado con NumPy: sin música con derechos de autor.
- **8 tipos de video** y modo 100 % aleatorio, con menú interactivo o CLI para automatizar.
- **Metadata lista para publicar**: cada video genera un `.txt` con título, descripción (con llamada a comentar),
  hashtags y las respuestas del reto.
- Duración fija de **63 s** (rango válido 61,5–65 s) para cumplir el mínimo de monetización In-Stream.

## Modos de video

| # | Modo | Mecánica | Interacción que se pide |
|---|---|---|---|
| 1 | **Reto de anomalía** | Rejilla de figuras donde una difiere (color, tamaño, brillo, punto o giro); dificultad creciente | ¿En qué segundo lo notaste? |
| 2 | **Ilusión óptica** | 5 de 6 ilusiones: Ouchi, café wall, Ebbinghaus, rejilla centelleante, espiral, muaré; se «desenmascaran» al final | ¿Cuántas te engañaron? |
| 3 | **Bucle infinito** | Bucle geométrico perfecto (el último frame empalma con el primero, audio incluido) | ¿Cuántas veces lo repetiste? |
| 4 | **Sincronización** | Una figura gira a velocidad extrema y encaja en una silueta en **un solo frame** | ¿En qué número del contador pausaste? |
| 5 | **Test de visión (Ishihara)** | Voronoi fluctuante con un número o figura oculto por una ligera variación de tono | ¿Qué número/figura viste? |
| 6 | **Enjambre** | Una partícula roja 2 s, se iguala, se mezclan y se detienen | ¿Dónde quedó el punto rojo? |
| 7 | **Ojo mágico** | Autoestereograma real con una figura 3D distinta en cada prueba | ¿Qué figura viste? |
| 8 | **Contraste simultáneo** | Bloque de color constante sobre un fondo que cambia; al revelar el bloque desaparece | ¿Cambió o no? |
| 9 | **Aleatorio** | La semilla elige entre los 8 tipos anteriores | — |

## Requisitos

| Componente | Requisito |
|---|---|
| Sistema operativo | Windows 10/11 (probado en Windows 11). Linux/macOS no verificados |
| Python | 3.10 o superior (probado con 3.14) |
| FFmpeg y FFprobe | Versión reciente en el `PATH`. Para NVENC, una compilación con soporte `nvenc` (p. ej. *full build*) |
| GPU | Cualquier GPU con OpenGL 3.3. Recomendada NVIDIA RTX para NVENC; sin ella se usa `libx264` |
| Red | Solo para sintetizar voz con edge-tts (las voces se guardan en caché local) |
| Disco | ~80 MB por video generado |

## Instalación

### Opción A: automática (Windows)

Haz doble clic en `iniciar.bat` (o ejecútalo desde una terminal). La **primera vez** el script:

1. Comprueba Python y, si falta, lo instala con `winget`.
2. Crea el entorno virtual `.venv` e instala las dependencias de `requirements.txt`.
3. Comprueba FFmpeg y, si falta, lo instala con `winget` (`Gyan.FFmpeg`).
4. Abre el menú interactivo.

En las siguientes ejecuciones solo instala lo que haya cambiado.

> Si `winget` instala Python o FFmpeg, cierra la ventana y vuelve a ejecutar `iniciar.bat` para que Windows
> actualice el `PATH`.

### Opción B: manual

```powershell
git clone https://github.com/yemsy26/Paradoja-Infinita.git
cd Paradoja-Infinita

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

winget install -e --id Gyan.FFmpeg      # o instala FFmpeg manualmente y agrégalo al PATH
```

Verifica FFmpeg y NVENC:

```powershell
ffmpeg -hide_banner -encoders | Select-String nvenc
```

## Uso

### Menú interactivo

```powershell
python main.py
```

```text
  [1] Reto de anomalia      [5] Test de vision
  [2] Ilusion optica        [6] Seguimiento enjambre
  [3] Bucle infinito        [7] Ojo magico
  [4] Sincronizacion        [8] Contraste simultaneo
  [9] 100% aleatorio        [0] Salir
```

Tras elegir un modo se pregunta la semilla (Enter = aleatoria) y la cantidad de videos.

### Línea de comandos (automatización)

```powershell
python main.py --mode random --count 5            # 5 videos con tipo aleatorio
python main.py --mode swarm --seed 12345          # reproducible
python main.py --mode loop --duration 64 --voice es-MX-DaliaNeural --codec hevc_nvenc
```

| Opción | Descripción | Por defecto |
|---|---|---|
| `--mode` | `anomaly`, `illusion`, `loop`, `sync`, `ishihara`, `swarm`, `magiceye`, `contrast`, `random`. Omite el menú | — (menú) |
| `--count` | Videos a generar con `--mode` (la semilla se incrementa si se fija `--seed`) | `1` |
| `--seed` | Semilla entera. Misma semilla + mismo modo = mismo video | aleatoria |
| `--duration` | Duración en segundos (61,5–65) | `63` |
| `--voice` | Voz de edge-tts (`edge-tts --list-voices`) | `es-MX-JorgeNeural` |
| `--codec` | `auto`, `h264_nvenc`, `hevc_nvenc`, `libx264` | `auto` |
| `--out` | Carpeta de salida | `output` |
| `--keep-work` | Conserva audio, subtítulos y log de FFmpeg | no |

## Salida generada

Cada video se guarda en su propia carpeta, dentro de la carpeta de la fecha:

```text
output/
└── 2026-11-15/
    └── anomalia_estrella_3380163066/
        ├── anomalia_estrella_3380163066.mp4
        └── anomalia_estrella_3380163066.txt
```

El nombre sigue el patrón `<modo>_<detalle>_<semilla>` (por ejemplo `ilusion_espiral_998877`, `ishihara_74_8`,
`ojomagico_rombo_101`). El `.txt` contiene el borrador de publicación:

```text
TIPO DE VIDEO:       Reto de Anomalía
VARIABLES:           semilla, paleta, figura, respuestas de cada prueba (control interno)
TÍTULO SUGERIDO:     ...
DESCRIPCIÓN (COPY):  ... (con llamada a comentar adaptada al modo)
HASHTAGS:            3-5 etiquetas del modo, siempre #ParadojaInfinita
```

Los textos varían según la semilla para no repetir títulos ni descripciones.

## Qué cambia con la semilla

| Elemento | Variación |
|---|---|
| Paleta | 5: neón cyberpunk, tonos cálidos, blanco y negro, océano, ácido tóxico (también colorean subtítulos y HUD) |
| Figura | círculo, triángulo, rombo, hexágono, estrella, pentágono, cuadrado |
| Layout | 4 tamaños de rejilla, normal u hexagonal, 4 estilos de movimiento y de fondo, giro |
| Velocidad | 0,5×–1,9× en fondo, figuras y gancho |
| Estructura | gancho de 4/5/6 s con 3 escenas, 4 o 5 actos, cierre de 3/3,5 s |
| Guion | frases y género gramatical adaptados a la figura y al reto |

## Rendimiento y GPU

Un video de 63 s (3780 frames) tarda entre 45 y 90 s en un portátil con Intel UHD + RTX 4060.

En portátiles con gráfica dual, Windows puede asignar la GPU integrada a Python (el programa avisa al arrancar).
Funciona igual, pero se acelera asignando la RTX: *Configuración → Sistema → Pantalla → Gráficos → Examinar →*
`.venv\Scripts\python.exe` *→ Opciones → Alto rendimiento*.

## Solución de problemas

| Síntoma | Causa probable y solución |
|---|---|
| `ffmpeg` / `ffprobe` no se reconoce | No está en el `PATH`. Instálalo (`winget install Gyan.FFmpeg`) y reinicia la terminal |
| Avisa «OpenGL no usa la RTX» | Ver [Rendimiento y GPU](#rendimiento-y-gpu). Es solo un aviso de velocidad |
| `h264_nvenc` falla o no existe | Sin GPU NVIDIA o FFmpeg sin NVENC: usa `--codec libx264` (modo `auto` lo hace solo) |
| Error de red al generar la voz | edge-tts necesita Internet la primera vez; las frases se cachean en `.cache/tts` |
| `moderngl` no crea el contexto | Controlador de vídeo desactualizado o sin OpenGL 3.3. Actualiza el controlador |
| Los subtítulos salen con otra fuente | Falta *Arial Black*; instálala o cambia la fuente en `paradoja/subtitles.py` |
| El ojo mágico no se ve en la plataforma | La recompresión de la red social degrada el patrón de puntos; prueba con un video piloto |

## Desarrollo y pruebas

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Las pruebas cubren la lógica pura (escena, línea de tiempo, guion, metadata) y no requieren GPU, FFmpeg ni red.
La integración continua las ejecuta en cada *push* y *pull request*. Consulta [CONTRIBUTING.md](CONTRIBUTING.md) y la
[documentación de arquitectura](docs/ARQUITECTURA.md).

## Estructura del proyecto

```text
main.py                  Menú interactivo / CLI
iniciar.bat              Lanzador con instalación automática (Windows)
paradoja/
  config.py              Constantes y VideoSpec (1080x1920, 60 fps)
  scene.py               Semilla → paleta, figura, actos, parámetros por modo
  timeline.py            Tiempo → uniforms del shader y eventos de sonido
  renderer.py            OpenGL headless (moderngl) → frames RGB24
  shaders/scene.frag     Todos los modos en GLSL
  script_es.py, tts.py   Guion por modo + síntesis de voz con tiempos por palabra
  audio.py               Drone y efectos procedurales
  subtitles.py           Subtítulos ASS y HUD
  encoder.py             FFmpeg: pipe crudo + mezcla + subtítulos → NVENC
  metadata.py            Nombres de archivo y borrador de publicación (.txt)
tests/                   Pruebas automatizadas
docs/ARQUITECTURA.md     Diseño interno y cómo añadir un modo
```

## Aviso legal

- El software se entrega «tal cual», sin garantías (ver [LICENSE](LICENSE)).
- La voz se sintetiza con el servicio en línea de Microsoft Edge a través de la biblioteca de terceros `edge-tts`,
  que no es un producto oficial: revisa sus condiciones de uso antes de uso comercial.
- Eres responsable de que el contenido publicado cumpla las políticas de la plataforma de destino.
- Este proyecto no está afiliado a Meta, Microsoft, NVIDIA ni FFmpeg.

## Licencia

Distribuido bajo la licencia [MIT](LICENSE). Creado por [yemsy26](https://github.com/yemsy26).
