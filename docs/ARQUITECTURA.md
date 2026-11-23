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
copy_es.py (pools) ─► spin.py (expande {a|b} con el rng de la semilla) ─► scene / acts / script_es / subtitles / metadata
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
| apertura 2,5-4,4 s | acto 1 | acto 2 | … | acto N | cierre 4-5 s |      (N = 4-7, duraciones variables)
                         └ búsqueda (largo − R) ┘└ revelación R ┘      (R = `TypeInfo.reveal`: 3 s, 3,5 s en los retos con
                                                                       texto y 5 s en cálculo y acertijo, por el debate)
```

Un video es una lista de **actos** (`scene.Act`); cada acto es un reto de un tipo (`scene.TYPES`). Un video de tipo único
repite el tipo; el video `mix` combina tipos distintos. La **apertura** (`Scene.lead`, 2,5–4,4 s según lo que dure el
gancho hablado) deja el primer reto ya formado y quieto mientras suena y se lee el gancho (`Scene.hook`); los actos
empiezan en `lead`. El **cierre** (`Scene.outro_len`, 4–5 s) narra y quema la llamada a seguir (`Scene.cta`), y pide
comentar el puntaje y compartir.

`acts._plan` reparte los 59,5-60 s disponibles entre los actos escalando la duración base de cada tipo
(`TypeInfo.base_len`). `acts.build_acts` llama al constructor del tipo, que devuelve todo lo que el acto necesita:
parámetros del shader, **narración** (`voice`), **texto en pantalla** (`items`), pregunta y respuesta.

El modo `loop` no tiene actos: toda la animación es periódica con periodo `duración / k`.

## Convenciones del shader (`shaders/scene.frag`)

- `px.y` crece **hacia abajo**: la fila 0 de `glReadPixels` es el borde superior del video, así no hace falta `vflip`.
- `u_scene` selecciona el tipo de reto **del acto actual** (`TypeInfo.scene_id`); la rejilla (`u_grid`, `u_cell`, `u_hex`)
  también es por acto. `u_kind` es la variante dentro del tipo.
- `u_pop` (0–1) escala/desvanece la escena al entrar y salir del acto (el primer acto entra ya formado: el primer fotograma sirve de miniatura); `u_reveal` (0–1) activa la revelación.
- `u_actph` es el reloj de movimiento del acto: se congela al empezar la revelación (en `count`, 2 s antes, para poder contar; excepto en `swarm`, donde es la
  integral de una velocidad con rampa y frenada, ver `scene.swarm_clock`).
- Las figuras comparten SDF (`shapeSDi`) para que el vocabulario geométrico sea común a todos los modos.
- Los textos nunca se dibujan en el shader (excepto las etiquetas numéricas de la revelación del conteo y de los vasos): van en ASS.
- Los retos de texto (`u_scene = 10`) dibujan una tarjeta de lectura (`u_q` = semialto y centro) y símbolos flotantes según `u_kind`
  (0 acertijo, 1 colores, 2 cálculo, 3 secuencia).
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

## Textos por semilla

`spin.spin(rng, plantilla, **huecos)` expande los grupos `{a|b|c}` (anidados, de dentro hacia fuera) con `rng.choice` y
rellena los huecos `<nombre>`. `copy_es.py` guarda los pools (ganchos, llamadas a seguir, debate, fragmentos de título,
descripción y hashtags) y las funciones `make_*` que eligen de ellos.

- `scene.build_scene` usa un generador aparte para ganchos y llamadas (`seed ^ 0x7E27`): elegirlos no consume números
  del generador de los retos. El gancho se elige antes de repartir los actos porque su duración (`copy_es.hook_lead`)
  fija `Scene.lead` (y con él el tiempo disponible para los actos), así que cambiar los pools de ganchos cambia el
  reparto de actos de una semilla; el hueco `<n>` (número de retos) se rellena después.
- Debate: `acts._debate` recibe la respuesta y, si existe, la **trampa** (respuesta común equivocada). Las familias de
  acertijos generados devuelven `(pregunta, respuesta, trampa)`; los de `acertijos.json` usan el campo opcional `"t"`.
  Sin trampa solo se pregunta al espectador. Nunca se afirman porcentajes ni hechos no comprobables.
- `metadata.build_post` compone el texto con fragmentos y calcula su huella (`post_hash`). Si la huella ya está en
  `output/historial.json` (o el título se usó hace poco) recompone con otra «sal» hasta 64 veces. Sigue siendo
  determinista para un mismo historial.
- Para añadir variantes: agrega plantillas a `copy_es.py`. Las pruebas de `tests/test_copy.py` validan que no queden
  `{`, `<` ni `|`, que quepan en pantalla y que las llamadas de cierre pidan seguir.

## Imágenes del feed

`generador_imagenes.py` → `feed/studio.py` (`generate_one`) → `puzzles.generate` (reto con respuesta comprobada) →
`render.render` (Pillow) + `copy_feed.build_post` (texto) → PNG/JPG + `.txt`. Es independiente del pipeline de video (no
usa GPU ni FFmpeg) y solo comparte `spin.py`, `copy_es.BRAND_TAG` y `acts._gen_seq` (familias de secuencias).

- `puzzles.py` no importa Pillow: cada generador devuelve un `Puzzle` (datos de dibujo, `answer`, `trap`, `explanation`,
  `key`). Con `avoid` (firmas del historial) se vuelve a sortear. Los cubos se rasterizan en un mapa de ids con el algoritmo
  del pintor (`analyse`) para saber cuáles quedan ocultos y que cada columna se vea por arriba.
- `canvas.py` dibuja a doble resolución (SS = 2) y reduce con LANCZOS; `Canvas.text` ajusta el tamaño de letra a la caja,
  con contorno y relieve. Las caritas y la flecha se dibujan con formas, así que no dependen de una fuente de emojis.
- `fonts.py` busca fuentes en `fonts/`, en las del usuario y en las del sistema, y solo acepta las que tienen los signos
  necesarios; sin ninguna usa la de Pillow. Para añadir un modo: generador en `puzzles.py` (+ `GENERATORS`), función
  `draw_*` en `render.py` (+ `DRAWERS`), plantillas en `copy_feed.py` y una opción en el menú.

## Elección inteligente

`catalog.choose` genera 24 semillas candidatas, construye cada escena (barato: no renderiza) y puntúa su novedad frente a
`output/historial.json` (tipos usados recientemente, formato, paleta, figura, acertijos y títulos). Elige la mejor. La
semilla elegida se guarda en el nombre del video, así que sigue siendo reproducible.

## Límites conocidos

- El render usa el contexto OpenGL por defecto de Windows; en portátiles con dos GPU puede ser la integrada.
- Los guiones están en español. Soportar otros idiomas implica un módulo equivalente a `script_es.py`.
- `edge-tts` requiere conexión a Internet la primera vez que se sintetiza cada frase.
