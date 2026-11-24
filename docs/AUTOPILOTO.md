# Autopiloto

`autopiloto.py` se queda en marcha y, cada día, **genera y publica solo** en tu página de Facebook, en las franjas que
configures (por defecto una de cada tipo):

| Franjas (`.env`) | Límite diario | Qué hace | Cómo |
|---|---|---|---|
| `HORARIOS_FOTOS=11:30` | `MAX_FOTOS_DIA=1` | **Imágenes** del feed | `generador_imagenes.py --modo aleatorio` → `POST /{page_id}/photos` |
| `HORARIOS_VIDEOS=18:00` | `MAX_VIDEOS_DIA=1` | **Reels** | `main.py --mode random` → `POST /{page_id}/video_reels` (inicio, subida y finalización) |

Cada lista admite **varias horas separadas por comas** (`HORARIOS_FOTOS=09:00,13:30,20:00`) y cada tipo tiene su **propio
límite diario**. A cada franja se le suma un **retraso aleatorio de 1 a 15 minutos** (distinto cada vez y cada día). El texto
sale del `_publicar.txt` más reciente que dejó el generador. Todo queda en `autopiloto.log` y cualquier error se registra
sin detener el programa. Lo publicado cada día se guarda en `estado_autopiloto.json`: ver «Estado diario y reinicios».

## 1. Credenciales (`.env`)

Copia `.env.example` como `.env` (está en `.gitignore`: **nunca lo subas ni lo compartas**) y rellena:

```text
PAGE_ID=123456789012345
PAGE_ACCESS_TOKEN=tu_token_de_pagina_de_larga_duracion
```

Qué necesitas (los paneles de Meta cambian a menudo: contrasta con la
[documentación oficial](https://developers.facebook.com/docs/video-api/guides/reels-publishing)):

- Una **página** de Facebook de la que seas administrador (los Reels solo se publican en páginas, no en perfiles).
- Una **app** en [developers.facebook.com](https://developers.facebook.com/apps) en la que seas administrador, con los
  permisos `pages_show_list`, `pages_read_engagement` y `pages_manage_posts`. Con la app en modo desarrollo y tú como
  administrador de la app y de la página no suele hacer falta revisión de la app; compruébalo en su panel.
- Un **token de página de larga duración**. La receta habitual:
  1. En el Explorador de la Graph API, con tu app, genera un token de usuario con esos tres permisos.
  2. Cámbialo por uno de larga duración:
     `GET https://graph.facebook.com/v26.0/oauth/access_token?grant_type=fb_exchange_token&client_id={app-id}&client_secret={app-secret}&fb_exchange_token={token-corto}`
  3. Con ese token llama a `GET /me/accounts`: ahí aparecen tus páginas, cada una con su `id` (= `PAGE_ID`) y su
     `access_token` (= `PAGE_ACCESS_TOKEN`). Un token de página obtenido así no debería caducar; verifícalo en el
     [depurador de tokens](https://developers.facebook.com/tools/debug/accesstoken/) («Expira: Nunca»).
  El `app-secret` solo se usa en ese paso: no lo pongas en el `.env`.

## 2. Primeras pruebas

```powershell
python autopiloto.py --check              # comprueba el token y muestra el nombre de tu página (no publica nada)
python autopiloto.py --dry-run --ahora foto   # genera una imagen y enseña qué publicaría, sin publicar
python autopiloto.py --ahora foto         # publica de verdad UNA imagen, ya
python autopiloto.py --ahora video        # publica de verdad UN Reel, ya
python autopiloto.py --estado             # lo publicado hoy, plantillas usadas, intervalo y lo pendiente (solo lee)
python autopiloto.py                      # modo autopiloto: se queda esperando las franjas
```

En Windows, `iniciar_autopiloto.bat` hace lo mismo (comprueba el entorno, el `.env` y FFmpeg). Se puede cambiar todo en el
`.env` o con opciones (ganan al `.env`): `--fotos 09:00,17:30 --videos 19:30 --max-fotos 2 --max-videos 1 --jitter 2-10 --dry-run`.

## 3. Cómo funciona

- **Retraso aleatorio.** A la hora base se elige un retraso entre `JITTER_MIN` y `JITTER_MAX` minutos (con segundos) y la
  publicación real se programa para entonces. Es cosmético: evita publicar siempre en el mismo segundo, pero **no
  protege frente a las normas de Meta** (contenido original, spam, contenido repetitivo). Lo que protege es el ritmo
  bajo, el contenido propio y usar la API oficial.
- **Sin duplicados.** `estado_autopiloto.json` recuerda lo publicado cada día (ver la sección siguiente): si cierras el
  programa o reinicias Windows no repite nada. `MAX_FOTOS_DIA` y `MAX_VIDEOS_DIA` limitan cada tipo por separado. Un candado
  (`autopiloto.lock`) impide dos autopilotos a la vez.
- **Errores.** Un fallo del render o de la API se anota en el log y el programa sigue vivo para la siguiente tarea. Los
  fallos temporales (límite de llamadas, errores 5xx de Meta antes de recibir nada) se reintentan hasta `REINTENTOS`
  veces cada `REINTENTO_MIN` minutos **sin volver a renderizar**. Si no se sabe si Meta recibió la publicación (se cortó
  la conexión justo al enviarla), se marca como *ambigua* y **no se reintenta** para no duplicarla: revisa tu página.
- **Reels.** Se sigue la guía oficial: `upload_phase=start`, subida a `rupload.facebook.com` con las cabeceras
  `Authorization: OAuth`, `offset` y `file_size` (un solo cuerpo; si se corta se reanuda desde `bytes_transfered`) y
  `upload_phase=finish` con `video_state=PUBLISHED`. Después espera a que Meta lo procese. Antes de subir se comprueba con
  `ffprobe` que cumple lo que pide Meta (9:16, mínimo 540×960, 24–60 fps, 3–90 s, AAC 48 kHz). Los Reels se envían con
  `is_ai_generated=true` solo si pones `IA_ETIQUETA=1`. **Por defecto (`IA_ETIQUETA=0`) no se envía ese parámetro en ninguna
  fase.** Meta pide declarar el contenido realista creado o alterado digitalmente (y la voz de los Reels es sintética): es
  una decisión tuya; comprueba la política vigente.
- **Fotos.** Se publican con `caption` (el copy) y, si la API lo acepta, `alt_text_custom` (el texto alternativo).
- **Zona horaria y PC.** Las horas son las del PC. Si una franja pasó mientras el PC estaba apagado o dormido, se recupera
  al volver si han pasado menos de `TOLERANCIA_HORAS` (3 por defecto) y todavía queda cupo; si no, se omite (no se publica
  de madrugada «para recuperar»).

## 3b. Estado diario y reinicios

Al arrancar, el autopiloto **lee `estado_autopiloto.json`**, muestra en la consola el resumen de hoy y **programa solo las
franjas pendientes que caben en el límite diario** de cada tipo:

```text
Resumen de hoy (2026-11-23): fotos 1/1 | videos 0/1
  Publicado:
    11:41:08  foto   fracciones_3-4_1234567890.png  id 1234567890_9876543
  Franja foto  11:30: ejecutada a las 11:41:08
  Franja video 18:00: pendiente, prevista a las 18:09:42
Pendiente por publicar hoy: 1 franja(s).
```

Qué guarda el archivo, por día (`YYYY-MM-DD`): cuántas `fotos` y `videos` se publicaron, la lista de `publicaciones` (tipo,
franja, hora, archivo, id de Meta y si fue `ok` o `ambiguo`) y el estado de cada franja (`programada`, `en_curso`,
`ejecutada`, `ambigua`, `error` u `omitida` con su motivo). Se conservan 45 días. Reglas:

- **Escritura atómica.** Cada cambio se escribe en un temporal, se fuerza a disco y se sustituye el archivo de golpe
  (`os.replace`), dejando antes una copia `estado_autopiloto.json.bak`. Un corte de luz a mitad de un guardado nunca deja el
  archivo a medias. Si aun así se dañara, se aparta como `*.corrupto-FECHA` y se recupera la copia `.bak`.
- **Anotación previa.** Justo antes de hablar con Meta, la franja queda como `en_curso` en disco. Si el programa muere en
  ese momento, al volver esa franja pasa a **ambigua** (pudo publicarse) y **no se repite sola**: revisa tu página.
- **Cupo por tipo.** Se programan, por orden de hora, las franjas pendientes mientras queden publicaciones en el límite de
  su tipo (lo ya publicado, también a mano con `--ahora`, gasta cupo). Las que no caben o pasaron hace más de la tolerancia
  se anotan como `omitida` con el motivo. Si subes un límite y reinicias, se vuelven a evaluar.
- **Lo publicado a mano también cuenta.** Una publicación que no salió de una franja de hoy (con `--ahora`, migrada del
  formato antiguo o de una franja que ya no está en el `.env`) **cubre la franja más cercana**: la última que había
  empezado antes de publicarse o, si fue antes de todas, la primera. Así, si ya subiste un Reel a las 13:53 y tienes las
  franjas 12:30 y 19:30, la de las 12:30 queda como «cubierta por una publicación manual» en vez de «recuperarse» a
  los pocos minutos, y la de las 19:30 sigue en pie.
- **Separación mínima entre publicaciones.** `MIN_INTERVALO_MINUTOS` (180 por defecto; 0 la desactiva) es la distancia mínima
  entre dos publicaciones **de cualquier tipo, incluidas las de `--ahora`**. Se aplica en tres sitios: al planificar (las franjas
  se retrasan hasta cumplirla; la que quedaría fuera de su margen o del día se omite), antes de generar (una franja
  que llega demasiado pronto se aplaza hasta que se cumpla) y justo antes de publicar (si salió otra mientras se generaba,
  el archivo espera sin volver a renderizarse). `--ahora` es una orden expresa: publica igualmente y lo avisa en el log. Con
  horarios como `10:00`, `14:30` y `19:30` el intervalo ni se nota; con franjas más juntas se van retrasando.
- **Plantillas sin repetir.** Cada publicación guarda en el estado su plantilla (el tipo de imagen —`pemdas`, `cubos`,
  `fracciones`, `opciones`— o el formato del video). Al generar, el autopiloto pasa las de hoy al generador con
  `--evitar` y, si aun así saliera repetida, descarta el resultado y genera otro (hasta 3 intentos); solo se vuelve a
  permitir una plantilla cuando ya se usaron todas.
- **Política de texto.** Antes de publicar se comprueba el texto con `copy_guard.py`: si menciona la IA o contiene cebos
  de interacción (cifras inventadas, «la mayoría falla», «comenta...», «etiqueta a...», «compártelo...»), se descarta y se genera
  otro (3 intentos; si todos fallan, esa franja queda con error y no se publica).
- **Misma hora tras reiniciar.** La hora elegida (franja + retraso aleatorio) queda guardada: un reinicio antes de esa hora
  la conserva en vez de sortear otra. Si ya pasó (el PC estaba apagado), se publica enseguida.
- **Errores.** Una franja con error (render o rechazo de la API: no llegó a publicarse) se vuelve a intentar al reiniciar,
  hasta 3 veces al día. Un archivo ya subido nunca se vuelve a publicar.
- **Medianoche.** Al cambiar de día se vuelve a planificar con los contadores del día nuevo, sin reiniciar.
- **Migración.** Si existe el `autopiloto_estado.json` de versiones anteriores, la primera vez se importa lo publicado hoy
  (el archivo antiguo no se toca).
- `--estado` solo lee: puedes ejecutarlo con el autopiloto en marcha.

## 4. Dejarlo en segundo plano (Windows)

- Ejecuta `iniciar_autopiloto.bat` y **minimiza** la ventana (no la cierres).
- Para que arranque con Windows: `Win + R` → `shell:startup` y pon allí un acceso directo a `iniciar_autopiloto.bat`
  (ejecutar minimizado), o crea una tarea en el *Programador de tareas* «al iniciar sesión».
- Desactiva la suspensión del PC (Configuración → Sistema → Energía): dormido no publica. El render del Reel usa la GPU.

## 5. Errores frecuentes

| Mensaje en el log | Qué hacer |
|---|---|
| `código 190` | El token es inválido o caducó: genera uno nuevo y ponlo en `PAGE_ACCESS_TOKEN`. |
| `código 200` / `283` | Faltan permisos o tu usuario no puede crear contenido en la página. |
| `código 368` | Meta marcó la acción como abusiva: para el autopiloto, revisa la página en Meta Business Suite y baja el ritmo. |
| `1363040` / `1363127` / `1363128` / `1363129` | El video no cumple relación de aspecto, resolución, duración o fps (el autopiloto lo detecta antes con `ffprobe`). |
| `resultado AMBIGUO` | Mira tu página: si la publicación está, no hagas nada; si no, usa `--ahora`. |
| `le faltan módulos: moderngl...` | Al Python de los generadores le faltan paquetes. El autopiloto usa el `.venv` del proyecto si existe (da igual desde qué entorno lo lances); si no, ejecuta el `pip install -r requirements.txt` que indica el mensaje, o usa `iniciar_autopiloto.bat`. |
| `FFmpeg/ffprobe no están en el PATH` | Ejecuta `iniciar.bat` una vez (instala FFmpeg con winget); el autopiloto lo encuentra solo en esa carpeta. |
| `No se pudo generar ...` | Falló `main.py` o `generador_imagenes.py` (GPU, FFmpeg, red de la voz): el log trae las últimas líneas. |

## 6. Límites

- Los Reels por API tienen un máximo de **30 cada 24 h** (`MAX_VIDEOS_DIA` admite de 0 a 30; con 0 o sin horas, ese tipo
  queda desactivado). Sube el ritmo con cuidado: Meta penaliza el spam y el contenido repetitivo.
- No cambia la miniatura del Reel, no publica el comentario con la respuesta ni etiqueta las fotos como IA (se dibujan por
  código, no con IA generativa).
- Seguridad: el token no se imprime ni se guarda en el log (se sustituye por `***`). Si crees que se filtró, revócalo desde
  la configuración de tu app y genera otro.

## 7. Diagnóstico: ¿se distribuyen igual los Reels de la API y los subidos a mano?

`comparar_reels.py` responde con datos (solo hace peticiones GET: no publica, no edita, no borra):

```powershell
python comparar_reels.py                      # tabla de Reels con vistas y edad + resumen autopiloto frente al resto
python comparar_reels.py --detalle 30         # más filas
python comparar_reels.py --manual 123 456     # marca esos ids de video como subidos a mano
python comparar_reels.py --no-guardar         # no guarda la foto de vistas de esta ejecución
```

- **Origen.** «autopiloto» = el id está en `estado_autopiloto.json`; el resto («otro») son los manuales y los anteriores al autopiloto.
- **Resumen.** Mediana, media, mínimo y máximo de vistas por grupo, usando solo Reels con una edad mínima (`--edad-min`, 6 h por
  defecto) para comparar lo comparable, y una lectura prudente: cuantifica la diferencia, no afirma la causa.
- **Fotos de vistas.** Cada ejecución guarda las vistas actuales en `diagnostico_reels.json` (en `.gitignore`: son métricas tuyas).
  Con varias fotos el informe rellena las columnas «a +1 h» y «a +24 h» de cada Reel, que es lo que se necesita para una prueba A/B.
- **Límites.** Con el permiso actual (`pages_read_engagement`) Meta solo deja leer `views` y los comentarios; las reproducciones, el
  tiempo medio visto y la retención piden `read_insights` o consultarlos a mano en Meta Business Suite. El token nunca se imprime.

### Prueba A/B limpia (autopiloto frente a manual)

1. Genera 6 videos de la misma plantilla y duración. Elige 3 para subir **a mano** y 3 para el **autopiloto** (`--ahora video`).
2. Alterna el orden y respeta 3 h entre publicaciones (`MIN_INTERVALO_MINUTOS`), para que la hora del día no favorezca a una vía.
3. Ejecuta `python comparar_reels.py` justo después de cada subida, a +1 h y a +24 h.
4. Compara las columnas «a +1 h» y «a +24 h» de cada vía. Si los del autopiloto se quedan en 1–2 y los manuales superan las decenas,
   el limitante es la visibilidad de lo que publica la API, no el archivo (ambas vías suben el mismo tipo de `.mp4`).
5. Comprueba la causa más probable: en developers.facebook.com abre tu app e interruptor «Modo». Según la documentación de Meta,
   solo los usuarios con rol ven lo que publica una app en **modo desarrollo**; al pasar a **modo activo** pasa a verse para todos.
   También puedes abrir el enlace de un Reel del autopiloto en una ventana de incógnito o con una cuenta sin rol.

