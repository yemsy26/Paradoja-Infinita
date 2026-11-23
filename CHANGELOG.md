# Changelog

Todos los cambios relevantes se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [1.7.1] - 2026-11-23

### Corregido
- Una publicación hecha a mano (`--ahora`), migrada del estado antiguo o de una franja que ya no está en el `.env` ahora
  **cubre la franja más cercana** en vez de gastar el cupo del día en la siguiente: con las franjas de vídeo 12:30 y 19:30 y
  un Reel ya subido a las 13:53, el autopiloto «recuperaba» el de las 12:30 al arrancar y se saltaba el de las 19:30.
  `--estado` y el resumen de arranque muestran esas franjas como «cubierta por una publicación manual/anterior».

## [1.7.0] - 2026-11-23

Autopiloto: estado diario persistente, varios horarios y límites independientes.

### Añadido
- **Estado diario en `estado_autopiloto.json`** (`paradoja/autopilot/state.py`): por cada día guarda cuántas fotos y vídeos
  se publicaron, qué archivo e id se subió y el estado de cada franja (`programada`, `en_curso`, `ejecutada`, `ambigua`,
  `error`, `omitida` con motivo). Escritura atómica (temporal + `fsync` + `os.replace`, con copia `.bak`), recuperación si el
  archivo se daña y migración automática del `autopiloto_estado.json` anterior.
- **Anotación previa a publicar**: la franja queda `en_curso` en disco antes de llamar a Meta. Si el programa muere o Windows
  se reinicia justo entonces, al volver pasa a *ambigua* y no se repite sola. Un archivo ya subido tampoco se repite.
- **Varias franjas y límites propios**: `HORARIOS_FOTOS` y `HORARIOS_VIDEOS` (listas separadas por comas) con
  `MAX_FOTOS_DIA` y `MAX_VIDEOS_DIA` independientes (`.env` y `.env.example`); opciones `--fotos`, `--videos`, `--max-fotos`
  y `--max-videos`.
- **Plan al arrancar**: se lee el estado, se muestra el resumen de hoy en la consola y se programan solo las franjas
  pendientes que caben en el límite de cada tipo (las demás se anotan como omitidas, con su motivo). Una franja pasada se
  recupera dentro de `TOLERANCIA_HORAS`; la hora elegida se conserva tras un reinicio; a medianoche se replanifica.
- `--estado`: muestra lo publicado hoy y lo pendiente sin publicar ni modificar nada (se puede usar con el autopiloto en marcha).

### Cambiado
- El candado se toma antes de leer el estado (un segundo autopiloto ya no puede alterar lo que el primero tiene en curso).
- `FOTO_HORA`, `VIDEO_HORA` y `MAX_POSTS_DIA` quedan en desuso (las dos primeras siguen valiendo con un aviso;
  `MAX_POSTS_DIA` se ignora).
- Pruebas de reinicio en `tests/test_autopilot.py`: cierre y reapertura sin duplicados, corte durante la generación y durante
  la publicación, escritura atómica, archivo dañado, migración, límites por tipo y cambio de día.

## [1.6.1] - 2026-11-23

### Corregido
- Al lanzar el autopiloto desde otro Python (conda, Python del sistema), el Reel fallaba con `No module named 'moderngl'`
  porque los generadores se ejecutaban con ese mismo Python (las imágenes no, porque solo necesitan Pillow). Ahora usan el
  Python del `.venv` del proyecto si existe, comprueban antes que tenga los módulos necesarios (con un mensaje claro y el
  comando para instalarlos) y añaden al PATH el FFmpeg instalado por winget cuando no está.

## [1.6.0] - 2026-11-23

Autopiloto: genera y publica solo en la página de Facebook.

### Añadido
- **`autopiloto.py`** (y `iniciar_autopiloto.bat`): orquestador con la librería `schedule`. Genera una imagen (11:30) con
  `generador_imagenes.py --modo aleatorio` y un Reel (18:00) con `main.py --mode random`, con un retraso aleatorio de 1 a 15
  minutos sobre cada hora. Opciones `--check`, `--dry-run`, `--ahora foto|video`, `--foto`, `--video` y `--jitter`.
- **Publicación por la Graph API** (v26.0, configurable): fotos por `/{page_id}/photos` (con `caption` y texto alternativo) y Reels
  por `/{page_id}/video_reels` (inicio, subida a `rupload.facebook.com` con reanudación por `offset`, finalización y espera del
  procesado), con `is_ai_generated=true`. Lee el texto del `_publicar.txt` más reciente.
- Credenciales en `.env` (`PAGE_ID`, `PAGE_ACCESS_TOKEN`; modelo en `.env.example`, fuera de Git). El token se enmascara en la
  configuración y se borra de los mensajes y del `autopiloto.log`.
- Robustez: `autopiloto.log` con rotación; un fallo del render o de la API no detiene el programa; reintentos solo de publicación
  y solo si es seguro (los resultados ambiguos no se repiten); estado por día para no duplicar al reiniciar y límite
  `MAX_POSTS_DIA`; bloqueo contra dos instancias; comprobación previa de los requisitos de Meta con `ffprobe`; las tareas
  atrasadas por un PC apagado no se publican a destiempo.
- Pruebas `tests/test_autopilot.py` con la API y los generadores simulados. Guía en `docs/AUTOPILOTO.md`.

### Cambiado
- Nuevas dependencias: `requests` y `schedule` (`requirements.txt` y CI).

## [1.5.0] - 2026-11-23

Imágenes estáticas para el feed de Facebook.

### Añadido
- **`generador_imagenes.py`** (menú interactivo y CLI) y `iniciar_imagenes.bat`: imágenes de 1080×1350 dibujadas con
  Pillow, sin IA generativa, con fondos vibrantes, texto grande con contorno y relieve y franja de «comenta tu respuesta»
  y «síguenos».
- 4 retos: **La Ecuación de la Discordia** (PEMDAS), **cubos isométricos** con cubos ocultos, **fracciones engañosas**
  (cuadrado, hexágono u octógono con triángulos partidos) y **opción múltiple tramposa** (números romanos parecidos,
  secuencias y preguntas clásicas), más un modo aleatorio que reparte los cuatro.
- Por imagen: `.txt` con el copy para pegar, la respuesta correcta (control interno), la explicación, la respuesta
  equivocada más común, el comentario para revelar la solución y el texto alternativo, y `_publicar.txt` con solo el copy
  (copiado al portapapeles en Windows). Carpeta `output_imagenes/AAAA-MM-DD/` e historial para no repetir retos ni textos.
- Fuentes TrueType: carpeta `fonts/`, estilos `montserrat`, `poppins`, `comic` e `impacto` y `--fuente`; sin ellas, las del
  sistema, comprobando que tengan × ÷ − ¿ ¡ ñ y tildes.
- Pruebas `tests/test_feed.py` (respuestas, visibilidad de los cubos, unicidad del copy, dibujo, archivos y menú).

### Cambiado
- Nueva dependencia: `pillow` (`requirements.txt` y CI). `copy_file_to_clipboard` pasa a `paradoja/clipboard.py`.

## [1.4.0] - 2026-11-22

Textos únicos por video (text spinning) para retención y seguidores, sin repetir nunca el mismo guion ni el mismo copy.

### Añadido
- **Motor de text spinning** (`paradoja/spin.py`): plantillas con grupos `{a|b|c}` y huecos `<n>`, expandidas con el
  generador de la semilla (misma semilla = mismo texto).
- **Pool de ganchos** (`paradoja/copy_es.py`, más de 600 variantes, genérico y por categoría del reto): se narra desde
  0,15 s y se muestra en una ficha grande. Nueva **apertura** de 2,5–4,4 s en la que el primer reto está quieto y visible.
- **Pool de llamadas a seguir** (más de 290 variantes, 65 en el bucle): se narra y se quema en pantalla durante los
  últimos 4–5 s; todas piden seguir la cuenta.
- **Debate en acertijos y cálculo**: en la revelación se enfrenta la respuesta común equivocada con la correcta («Muchos
  dicen X, pero es Y. ¿Tú qué opinas?») con una ficha en pantalla; sin trampa conocida solo se pregunta al espectador.
  Las familias de acertijos generados devuelven la trampa y 24 acertijos de `acertijos.json` llevan el campo opcional
  `"t"`. Línea previa «piénsalo bien» cuando hay hueco. Revelación de 5 s en cálculo y acertijo.
- **Texto de publicación por fragmentos** con huella en `output/historial.json`: título (esqueleto + apertura + cierre),
  descripción, pies de compartir/seguir, comentario fijado y hashtags (3–4 del tipo en orden aleatorio + la marca);
  si la huella coincide con una publicación reciente, se recompone.
- Pruebas `tests/test_copy.py` (motor, pools, debate, pantalla y unicidad del copy).

### Cambiado
- El cierre usa la llamada a seguir elegida por la semilla (antes una fija), con ficha grande bajo la marca; duración
  4, 4,5 o 5 s. El enunciado del primer reto de texto ya se lee durante el gancho.
- `write_metadata` devuelve también la huella del texto; `catalog.entry_for` la guarda y `catalog.recent_posts` la lee.
- Las semillas anteriores ya no reproducen el mismo video (cambian la apertura y el reparto de actos).

## [1.3.0] - 2026-11-22

Variedad de contenido, texto de publicación y aspecto de los retos de texto.

### Añadido
- **Acertijos**: de 34 a más de 120 en `content/acertijos.json` (los antiguos conservan su índice) y 11 familias de
  acertijos con números generados (edades, bate y pelota, campanadas, monedas…) que nunca repiten enunciado.
- **Secuencias**: 17 familias (cubos, alternadas, diferencias crecientes, ×m+k, potencias de 2…) con parámetros
  amplios: el nivel difícil pasa de 24 series posibles a miles; no se repite la misma serie dentro de un video.
- **Ilusiones**: 4 nuevas (rejilla de Hermann, Müller-Lyer, triángulo de Kanizsa y Zöllner), 10 en total.
- **Ojo mágico con números de dos cifras** en 3D, además de las 7 figuras.
- `<nombre>_publicar.txt` con solo el texto a pegar, copia automática al portapapeles en Windows (`--no-copy` lo
  desactiva) y bloque «COPIAR Y PEGAR» al inicio del `.txt`. Sin la etiqueta «HASHTAGS:» dentro del texto.
- Aviso de la **etiqueta de IA** de Meta (la voz es sintética) en la consola y en el `.txt`.

### Cambiado
- Títulos y descripciones: frase de búsqueda por tipo, pies de compartir/seguir rotativos y títulos genéricos
  adicionales (más de 40 combinaciones por tipo). En los acertijos el primer acertijo va en el título y se pide la
  respuesta. Reglas de Meta respetadas: sin enlaces, pocas mayúsculas, máximo 5 hashtags.
- Retos de texto (acertijo, colores, cálculo, secuencia): tarjeta de lectura con borde luminoso, símbolos flotantes
  (signos de interrogación, operadores, dígitos), ondas al revelar y viñeta. Gancho y respuesta como fichas de color
  de acento con texto de alto contraste. Los acertijos largos reducen la letra para no invadir otras zonas.

## [1.2.0] - 2026-11-20

Retención y alcance, a partir de las métricas de las primeras publicaciones (alcance estancado en el grupo de prueba
inicial y pocas reproducciones de 3 s) y de la documentación de Meta sobre contenido original y clasificación de Reels.

### Añadido
- **Gancho en el primer fotograma**: el reto entra ya formado (antes el primer fotograma era un fondo vacío, de ahí las
  miniaturas oscuras) y lleva un texto de gancho de 2,2 s según la categoría del primer reto.
- **Portada** (`<slug>_portada.jpg`) por video, para subirla como miniatura del Reel.
- 3 retos nuevos (17 en total): **Vasos** (¿dónde está la bola?), **Simón** (recuerda el orden de los pads, con un
  tic por destello) y **Número distinto** (dígitos casi idénticos, de fácil a difícil).
- Cierre ampliado: nota en comentarios, **compartir** con alguien y **seguir** la cuenta; indicador «FINAL» en el último
  reto; en la metadata, comentario fijado sugerido y aviso de la portada.

### Cambiado
- **Zona segura de Reels** (estimada: 14 % superior y 35 % inferior, comprobar en el móvil): etiqueta, cuenta atrás y
  pregunta bajan de la franja superior; las respuestas (celdas, objetivo del enjambre, figuras contadas) ya no caen bajo
  la pregunta fija ni bajo la zona de la app. Pregunta fija con caja semitransparente para leerse sobre cualquier fondo.
- Cierre de 4–4,5 s y mensajes hablados de cierre acordes. Rejillas de memoria sin la de 3×4 (dejaba solo 3 celdas
  válidas).

## [1.1.1] - 2026-11-17

Revisión de calidad de cada reto en el modo aleatorio.

### Cambiado
- **Pregunta siempre visible**: los retos visuales muestran su pregunta fija arriba durante la búsqueda y la respuesta
  corta durante la revelación (antes solo se oía).
- **Tiempos de revelación por tipo**: los retos con texto (cálculo, secuencia, acertijo, colores, conteo) dejan 3,5 s
  para leer la respuesta; cálculo y secuencia dan más tiempo de búsqueda. Cierre de 3,5–4 s.
- **Conteo rediseñado**: de 10 a 18 figuras (antes hasta 40), se mueven más despacio, se detienen 2 s antes de revelar
  y las que hay que contar quedan fuera de la franja de subtítulos y separadas entre sí.
- **Dificultad con suelo legible**: la dificultad ya no llega a hacer imposible un reto (Ishihara con contraste
  mínimo, memoria y «qué cambió» con cambios visibles; sin el cambio de «punto» casi invisible).
- Ilusión Café Wall: mortero fino y desfase estable, para que se vea la inclinación en lugar de un tablero.
- Narración: la cuenta atrás es «Tres, dos, uno.» y se omiten el gancho y las líneas intermedias cuando no caben,
  de modo que ninguna frase se pisa con la siguiente; frases de cierre más cortas.
- Cuenta atrás en la esquina, más pequeña, para no tapar el reto.

### Corregido
- El muestreo del conteo podía tardar varios segundos por video.

## [1.1.0] - 2026-11-16

### Añadido
- 7 retos nuevos: conteo, qué cambió, memoria, efecto Stroop, cálculo, secuencia y acertijo (14 en total).
- Video **mixto**: combina de 5 a 7 retos distintos en un mismo video.
- **Aleatorio inteligente** con historial (`output/historial.json`): elige el reto, formato, paleta, figura, acertijo y
  título menos usados recientemente. Menú reorganizado (aleatorio inteligente, mixto, reto concreto, estadísticas).
- Llamada a comentar el puntaje en el cierre de cada video; textos de la metadata para cada reto.
- `content/acertijos.json`: acertijos editables.

### Cambiado
- Estructura de los videos: el primer reto empieza en el segundo 0 (sin gancho largo) y hay de 4 a 7 actos de duración
  variable. Las semillas antiguas ya no reproducen exactamente el mismo video.
- Contraste simultáneo: 4 variantes con respuestas distintas (antes todas las pruebas terminaban en «nunca cambió»).
- Las figuras (triángulo, estrella) se dibujan con la punta hacia arriba.

### Corregido
- Los números del test de visión (Ishihara) se dibujaban invertidos verticalmente.

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
