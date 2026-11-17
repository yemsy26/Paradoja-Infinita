# Arquitectura

## Pipeline

```text
semilla ──► scene.py ──► Scene (paleta, figura, actos, parámetros)
                │
                ├─► timeline.py ──► uniforms por frame ──► renderer.py ──► frames RGB24 ─┐
                ├─► script_es.py ─► segmentos de texto ──► tts.py ─► clips + tiempos ────┤
                │                                          audio.py ─► cama sonora       ├─► encoder.py (FFmpeg + NVENC) ─► .mp4
                └─► subtitles.py ─► subs.ass ───────────────────────────────────────────┘
                └─► metadata.py ──► .txt de publicación
```

1. `scene.build_scene(seed, mode, spec)` es **determinista**: usa un único `random.Random(seed)`. Misma semilla y modo
   producen la misma escena. No añadas llamadas a `rng` en las ramas comunes sin tener en cuenta que cambian los
   videos de semillas antiguas.
2. `Timeline.uniforms(t)` convierte el instante `t` en valores para el shader. Es una función pura de `t`.
3. `GpuRenderer.frames()` renderiza un frame por iteración y entrega los bytes a `FfmpegEncoder`, que los escribe en
   un hilo aparte (cola acotada) para solapar render y codificación.
4. El audio de voz se sintetiza por segmentos (cada uno en su instante) y se mezcla con la cama procedural dentro del
   mismo comando de FFmpeg (`adelay` + `amix`); los subtítulos ASS se queman con el filtro `ass`.

## Estructura temporal

```text
| acto 1 | acto 2 | … | acto N | cierre 3-3,5 s |      (N = 4-7, duraciones variables)
  └ búsqueda (largo − 3 s) ┘└ revelación 3 s ┘
```

Un video es una lista de **actos** (`scene.Act`); cada acto es un reto de un tipo (`scene.TYPES`). Un video de tipo único
repite el tipo; el video `mix` combina tipos distintos. No hay gancho largo: el primer reto empieza en el segundo 0
(la retención de los primeros segundos es lo que más pesa). El cierre muestra la marca y pide comentar el puntaje.

`acts._plan` reparte los 59,5-60 s disponibles entre los actos escalando la duración base de cada tipo
(`TypeInfo.base_len`). `acts.build_acts` llama al constructor del tipo, que devuelve todo lo que el acto necesita:
parámetros del shader, **narración** (`voice`), **texto en pantalla** (`items`), pregunta y respuesta.

El modo `loop` no tiene actos: toda la animación es periódica con periodo `duración / k`.

## Convenciones del shader (`shaders/scene.frag`)

- `px.y` crece **hacia abajo**: la fila 0 de `glReadPixels` es el borde superior del video, así no hace falta `vflip`.
- `u_scene` selecciona el tipo de reto **del acto actual** (`TypeInfo.scene_id`); la rejilla (`u_grid`, `u_cell`, `u_hex`)
  también es por acto. `u_kind` es la variante dentro del tipo.
- `u_pop` (0–1) escala/desvanece la escena al entrar y salir del acto; `u_reveal` (0–1) activa la revelación.
- `u_actph` es el reloj de movimiento del acto: se congela al empezar la revelación (excepto en `swarm`, donde es la
  integral de una velocidad con rampa y frenada, ver `scene.swarm_clock`).
- Las figuras comparten SDF (`shapeSDi`) para que el vocabulario geométrico sea común a todos los modos.
- Los textos nunca se dibujan en el shader (excepto las etiquetas numéricas de la revelación del conteo): van en ASS.
  Los dígitos de 7 segmentos usan `numSD`, que voltea la `y` (el SDF usa y hacia arriba, la imagen hacia abajo). Mantén el objetivo del reto fuera de la franja
  `config.SUB_BAND` (la que tapan los subtítulos).

## Detalles por modo

| Modo | Detalle técnico |
|---|---|
| `sync` | La figura usa una trayectoria de Lissajous con frecuencias inconmensurables y `tau = t − hit`. `tau == 0` solo en el frame del encaje (`hit` está alineado a frame). Al revelar, `tau` avanza en cámara lenta |
| `ishihara` | Voronoi con puntos animados; la máscara (dígitos de 7 segmentos o SDF de figura) se evalúa en el centro de cada celda. Ruido de color re-sorteado 3 veces por segundo |
| `swarm` | Hasta 40 partículas con posición analítica `p_i(s)`; los parámetros viajan en arrays de uniforms. `scene._swarm_act` re-muestrea hasta que el objetivo quede visible al detenerse |
| `magiceye` | Pasada 1 (`u_pass=1`): mapa de profundidad. La CPU integra `1/(P − k·d)` por fila → textura de fase `u_phi`. Pasada 2: patrón de puntos periódico en esa fase |
| `contrast` | Bloque de luminosidad constante; el fondo oscila según tres variantes. Al revelar el fondo se iguala al bloque |
| `loop` | Todas las fases son múltiplos enteros de 2π; el audio ajusta sus frecuencias a un número entero de ciclos |

## Cómo añadir un tipo de reto

1. `scene.py`: añade un `TypeInfo` a `TYPES` (id de escena, etiqueta, duración base, si lleva cuenta atrás, categoría).
2. `acts.py`: escribe el constructor `_mi_tipo(rng, ctx, a, st)` que devuelva los campos del `Act` (parámetros,
   `voice`, `items`, `question`, `answer`) y regístralo en `_BUILDERS`. Cuida que cada línea de `voice` quepa en su hueco.
3. `shaders/scene.frag`: si necesita una escena propia, escribe `miTipoScene(px)` y enlázala en `mainScene`; si solo es
   texto, reutiliza `u_scene = 10` y dibuja el texto con `items`.
4. `timeline.py`: añade uniforms por acto si hacen falta.
5. `metadata.py`: añade nombre, *slug*, hashtags y un constructor de títulos/descripciones que pida interacción.
6. `tests/`: las pruebas parametrizadas por `MODES` ya cubren determinismo, estructura, guion y metadata; añade las del tipo.
7. Documenta el reto en `README.md`, `README.en.md` y `CHANGELOG.md`.

## Elección inteligente

`catalog.choose` genera 24 semillas candidatas, construye cada escena (barato: no renderiza) y puntúa su novedad frente a
`output/historial.json` (tipos usados recientemente, formato, paleta, figura, acertijos y títulos). Elige la mejor. La
semilla elegida se guarda en el nombre del video, así que sigue siendo reproducible.

## Límites conocidos

- El render usa el contexto OpenGL por defecto de Windows; en portátiles con dos GPU puede ser la integrada.
- Los guiones están en español. Soportar otros idiomas implica un módulo equivalente a `script_es.py`.
- `edge-tts` requiere conexión a Internet la primera vez que se sintetiza cada frase.
