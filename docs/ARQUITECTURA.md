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
| gancho 4-6 s | acto 1 | acto 2 | … | acto N | cierre 3-3,5 s |      (N = 4 o 5)
                 └ búsqueda (act_len − 3 s) ┘└ revelación 3 s ┘
```

El modo `loop` no tiene gancho ni actos: toda la animación es periódica con periodo `duración / k`.

## Convenciones del shader (`shaders/scene.frag`)

- `px.y` crece **hacia abajo**: la fila 0 de `glReadPixels` es el borde superior del video, así no hace falta `vflip`.
- `u_scene` selecciona el modo (índice de `scene.MODES`). `u_kind` es la variante del acto actual.
- `u_pop` (0–1) escala/desvanece la escena al entrar y salir del acto; `u_reveal` (0–1) activa la revelación.
- `u_actph` es el reloj de movimiento del acto: se congela al empezar la revelación (excepto en `swarm`, donde es la
  integral de una velocidad con rampa y frenada, ver `scene.swarm_clock`).
- Las figuras comparten SDF (`shapeSDi`) para que el vocabulario geométrico sea común a todos los modos.
- Los textos nunca se dibujan en el shader: van en ASS. Mantén el objetivo del reto fuera de la franja
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

## Cómo añadir un modo nuevo

1. `scene.py`: añade el nombre a `MODES` (el índice será `u_scene`), a `HUD_LABEL` y, si usa cuenta atrás, a
   `HAS_COUNTDOWN`. Crea los `Act` del modo en `build_scene`.
2. `shaders/scene.frag`: escribe `miModoScene(px)` y enlázalo en `mainScene`.
3. `timeline.py`: si necesita uniforms por acto, añádelos en `Timeline.uniforms`.
4. `script_es.py`: añade el gancho y las frases (cuida que cada segmento quepa en su hueco; el log avisa de solapes).
5. `metadata.py`: añade etiqueta, *slug* y un constructor de título/descripción/hashtags que pida interacción.
6. `main.py`: añade la opción al menú.
7. `tests/`: las pruebas parametrizadas por `MODES` ya cubren determinismo, guion y metadata; añade las propias del modo.
8. Documenta el modo en `README.md`, `README.en.md` y `CHANGELOG.md`.

## Límites conocidos

- El render usa el contexto OpenGL por defecto de Windows; en portátiles con dos GPU puede ser la integrada.
- Los guiones están en español. Soportar otros idiomas implica un módulo equivalente a `script_es.py`.
- `edge-tts` requiere conexión a Internet la primera vez que se sintetiza cada frase.
