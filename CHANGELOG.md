# Changelog

Todos los cambios relevantes se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

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
