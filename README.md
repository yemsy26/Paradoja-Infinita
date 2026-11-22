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
- [Retos disponibles](#retos-disponibles)
- [Variedad y anti-saturación](#variedad-y-anti-saturación)
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
- **17 tipos de reto + video mixto + bucle perfecto**, con elección inteligente que evita repetir retos, menú
  interactivo o CLI para automatizar.
- **Pensado para retención y alcance**: el primer fotograma ya lleva el reto y un gancho en pantalla, el texto respeta
  la zona segura de Reels y cada video exporta una **portada** (`*_portada.jpg`) para usarla como miniatura.
- **Metadata lista para publicar**: cada video genera un `.txt` con título, descripción (con llamada a comentar y a
  compartir), comentario fijado sugerido, hashtags y las respuestas del reto.
- Duración fija de **63 s** (rango válido 61,5–65 s) para cumplir el mínimo de monetización In-Stream.

## Retos disponibles

Un video de **tipo único** repite el mismo reto (4-7 veces, con dificultad creciente). El **video mixto** combina de 5 a
7 retos *distintos*. Todos empiezan con el reto en el segundo 0, revelan la respuesta al final de cada prueba y cierran
con una llamada a comentar la nota, compartir y seguir la cuenta.

| Categoría | Reto | Mecánica | Qué se pide en comentarios |
|---|---|---|---|
| Visual | **Anomalía** | Rejilla de figuras donde una difiere (color, tamaño, brillo, punto o giro) | ¿En qué segundo lo notaste? |
| Visual | **Ilusión óptica** | 10 ilusiones: Ouchi, café wall, Ebbinghaus, rejilla centelleante, espiral, muaré, Hermann, Müller-Lyer, Kanizsa y Zöllner; se «desenmascaran» | ¿Cuántas te engañaron? |
| Visual | **Test de visión** | Voronoi fluctuante con un número o figura oculto por una ligera variación de tono | ¿Qué número/figura viste? |
| Visual | **Ojo mágico** | Autoestereograma real con una figura o un número de dos cifras en 3D distinto por prueba | ¿Qué figura viste? |
| Visual | **Contraste** | 4 variantes: ¿cambia el color? · ¿se aclara u oscurece? · ¿cuál es más oscuro? · ¿cuál es más claro? (la respuesta cambia según la prueba) | Tu respuesta antes de la revelación |
| Reflejos | **Sincronización** | La figura gira a velocidad extrema y encaja en una silueta en **un solo frame** | ¿En qué número del contador pausaste? |
| Atención | **Seguimiento** | Una partícula roja 2 s, se iguala, el enjambre se mezcla y se detiene | ¿Dónde quedó el punto rojo? |
| Atención | **Conteo** | «¿Cuántos triángulos azules hay?» entre figuras en movimiento; la revelación numera las correctas | Tu número |
| Atención | **Vasos** | El juego de los vasos: una bola bajo un vaso, los vasos se intercambian cada vez más rápido y se revela dónde quedó | 1, 2 o 3 (el hueco) |
| Atención | **Qué cambió** | Dos imágenes parpadean y una figura cambia (color, tamaño, giro, desaparece…) | Fila y columna del cambio |
| Visual | **Número distinto** | Rejilla de dígitos casi iguales (8/0, 6/5, 9/3…) con uno distinto; los pares se parecen más en cada prueba | ¿En qué segundo lo viste? |
| Memoria | **Simón** | Cuatro pads numerados se iluminan en secuencia (3-6 pasos); se pregunta por un paso y la revelación repite la secuencia | El número del pad |
| Memoria | **Memoria** | Memoriza 3 s, pantalla en blanco y la figura cambió | Qué figura cambió |
| Mente | **Efecto Stroop** | Palabras de color con tinta distinta: di el color de la tinta | ¿Cuántas fallaste? |
| Mente | **Cálculo** | Operaciones generadas con «trampa» de orden (el resultado obvio es incorrecto) | Tu resultado |
| Mente | **Secuencia** | «¿Qué número sigue?» (17 familias: aritméticas, geométricas, cuadrados, cubos, Fibonacci, alternadas, primos…; miles de series distintas) | El número que sigue |
| Mente | **Acertijo** | Más de 120 acertijos y preguntas trampa de `content/acertijos.json` (editable) más acertijos con números generados (edades, bate y pelota, campanadas…) que nunca se repiten | Tu respuesta |
| Especial | **Bucle infinito** | Perfect loop geométrico (el último frame empalma con el primero, audio incluido) | ¿Cuántas veces lo repetiste? |
| Especial | **Mixto** | 5-7 retos distintos en un solo video | Puntaje de 0 a N |

## Variedad y anti-saturación

El sistema está pensado para publicar varias veces al día sin repetir fórmula:

- **Contenido generado, no plantillas:** cada operación, secuencia, conteo, conjunto de palabras o tablero es nuevo, así que
  los retos de texto tienen variedad prácticamente ilimitada. Los acertijos salen de `content/acertijos.json`
  (añade los tuyos con el formato `{"q": "pregunta", "a": "respuesta"}`; ponlos al final para no alterar el historial) y
  de 11 familias con números generados. Las secuencias salen de 17 familias con parámetros amplios (el nivel difícil ya
  no son 24 series, sino miles).
- **Texto de publicación rotativo:** título, frase de búsqueda, llamada a comentar, a compartir y a seguir se combinan
  de forma distinta en cada video (más de 40 combinaciones por tipo), siguiendo la guía de Meta: sin enlaces, pocas
  mayúsculas y como máximo cinco hashtags.
- **Aleatorio inteligente:** para cada video se evalúan 24 semillas candidatas y se elige la más distinta de lo publicado
  recientemente (según `output/historial.json`): evita repetir el mismo reto, formato, paleta, figura, acertijo o título.
- **Video mixto:** cambia de reto cada 8-12 s, lo que mantiene la atención y multiplica las combinaciones.
- La misma semilla + el mismo formato siguen dando el mismo video (reproducible).

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
  [1] Aleatorio inteligente   (RECOMENDADO) elige el reto menos usado recientemente y evita repetir
  [2] Video mixto             5-7 mini-retos distintos en 1 video
  [3] Elegir un reto concreto (17 retos + bucle)
  [4] Estadisticas y ultimos videos
  [0] Salir
```

Para publicar a diario basta con la opción **[1]** y la cantidad de videos que quieras: cada uno se elige según el
historial. La opción **[3]** muestra los retos por categoría y pregunta la semilla (Enter = aleatoria).

### Línea de comandos (automatización)

```powershell
python main.py --mode random --count 5            # 5 videos variados (elección inteligente)
python main.py --mode mix --count 3               # 3 videos mixtos
python main.py --mode math --seed 12345           # un reto concreto, reproducible
python main.py --mode loop --duration 64 --voice es-MX-DaliaNeural --codec hevc_nvenc
```

| Opción | Descripción | Por defecto |
|---|---|---|
| `--mode` | `random`, `mix`, `loop` o un reto: `anomaly`, `illusion`, `ishihara`, `magiceye`, `contrast`, `sync`, `swarm`, `count`, `flicker`, `memory`, `stroop`, `math`, `sequence`, `riddle`. Omite el menú | — (menú) |
| `--count` | Videos a generar con `--mode` (la semilla se incrementa si se fija `--seed`) | `1` |
| `--seed` | Semilla entera. Misma semilla + mismo formato = mismo video | la más novedosa |
| `--duration` | Duración en segundos (61,5–65) | `63` |
| `--voice` | Voz de edge-tts (`edge-tts --list-voices`) | `es-MX-JorgeNeural` |
| `--codec` | `auto`, `h264_nvenc`, `hevc_nvenc`, `libx264` | `auto` |
| `--out` | Carpeta de salida | `output` |
| `--keep-work` | Conserva audio, subtítulos y log de FFmpeg | no |
| `--no-copy` | No copiar el texto de publicación al portapapeles (Windows) | copia |

## Salida generada

Cada video se guarda en su propia carpeta, dentro de la carpeta de la fecha:

```text
output/
└── 2026-11-15/
    └── anomalia_estrella_3380163066/
        ├── anomalia_estrella_3380163066.mp4
        ├── anomalia_estrella_3380163066_portada.jpg
        ├── anomalia_estrella_3380163066_publicar.txt
        └── anomalia_estrella_3380163066.txt
```

El nombre sigue el patrón `<formato>_<detalle>_<semilla>` (por ejemplo `ilusion_espiral_998877`, `ishihara_74_8`,
`calculo_operaciones_5`, `mixto_calculo-cambio-stroop_38`). El `.txt` contiene el borrador de publicación:

`<nombre>_publicar.txt` contiene **solo** lo que se pega en la publicación (título, descripción y hashtags, sin
etiquetas), y al terminar cada video ese texto queda **copiado en el portapapeles** (Windows; desactívalo con
`--no-copy`): basta con pegarlo con Ctrl+V. El `.txt` completo empieza con ese mismo bloque y añade lo demás:

```text
TIPO DE VIDEO:       Reto de Anomalía
VARIABLES:           semilla, paleta, figura, respuestas de cada prueba (control interno)
TÍTULO SUGERIDO:     ...
DESCRIPCIÓN (COPY):  ... (con llamada a comentar adaptada al modo + compartir + seguir)
COMENTARIO FIJADO:   pregunta sencilla de una cifra para pegar y fijar
PORTADA:             <slug>_portada.jpg (miniatura con el gancho a pantalla completa)
ANTES DE PUBLICAR:   aviso de la etiqueta de IA (ver abajo)
HASHTAGS:            3-5 etiquetas del modo, siempre #ParadojaInfinita
```

**Etiqueta de IA.** Meta exige usar su herramienta de divulgación en el contenido orgánico con audio de aspecto
realista creado digitalmente, y puede penalizar si no se declara ([anuncio de Meta](https://about.fb.com/news/2026/02/meta-prepares-for-2026-us-midterms/)).
La narración de estos videos es una voz neuronal sintética, así que lo prudente es activar la «Etiqueta de IA» al
publicar. Es una recomendación, no asesoría legal: comprueba la política vigente.

Los títulos y descripciones se eligen entre varias versiones y evitan repetir los usados recientemente. Cada video se
registra en `output/historial.json`, que usa la elección inteligente y la opción de estadísticas.

## Qué cambia con la semilla

| Elemento | Variación |
|---|---|
| Paleta | 5: neón cyberpunk, tonos cálidos, blanco y negro, océano, ácido tóxico (también colorean subtítulos y HUD) |
| Figura | círculo, triángulo, rombo, hexágono, estrella, pentágono, cuadrado |
| Layout | 4 tamaños de rejilla, normal u hexagonal, 4 estilos de movimiento y de fondo, giro |
| Velocidad | 0,5×–1,9× en fondo, figuras y gancho |
| Estructura | 4-7 actos de duración variable que rellenan los 63 s; cierre de 3,5/4 s; en el video mixto, qué retos y en qué orden |
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
  scene.py               Modelo de datos, tipos de reto y paletas
  acts.py                Generación de cada reto: parámetros, narración y texto en pantalla
  texts_es.py            Textos en español, números en palabras y gramática de figuras
  catalog.py             Historial y elección inteligente de retos
  timeline.py            Tiempo → uniforms del shader y eventos de sonido
  renderer.py            OpenGL headless (moderngl) → frames RGB24
  shaders/scene.frag     Todos los modos en GLSL
  script_es.py, tts.py   Guion del video + síntesis de voz con tiempos por palabra
  audio.py               Drone y efectos procedurales
  subtitles.py           Subtítulos ASS y HUD
  encoder.py             FFmpeg: pipe crudo + mezcla + subtítulos → NVENC
  metadata.py            Nombres de archivo y borrador de publicación (.txt)
content/acertijos.json   Acertijos editables
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
