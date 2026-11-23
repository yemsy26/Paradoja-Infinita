# Autopiloto

`autopiloto.py` se queda en marcha y, cada día, **genera y publica solo** en tu página de Facebook:

| Hora base | Qué hace | Cómo |
|---|---|---|
| 11:30 | Una **imagen** del feed | `generador_imagenes.py --modo aleatorio` → `POST /{page_id}/photos` |
| 18:00 | Un **Reel** | `main.py --mode random` → `POST /{page_id}/video_reels` (inicio, subida y finalización) |

A cada hora base se le suma un **retraso aleatorio de 1 a 15 minutos** (distinto cada vez y cada día). El texto sale del
`_publicar.txt` más reciente que dejó el generador. Todo queda en `autopiloto.log` y cualquier error se registra sin
detener el programa.

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
python autopiloto.py                      # modo autopiloto: se queda esperando las horas
```

En Windows, `iniciar_autopiloto.bat` hace lo mismo (comprueba el entorno, el `.env` y FFmpeg). Se puede cambiar todo en el
`.env` o con opciones: `--foto 10:00 --video 19:30 --jitter 2-10 --dry-run`.

## 3. Cómo funciona

- **Retraso aleatorio.** A la hora base se elige un retraso entre `JITTER_MIN` y `JITTER_MAX` minutos (con segundos) y la
  publicación real se programa para entonces. Es cosmético: evita publicar siempre en el mismo segundo, pero **no
  protege frente a las normas de Meta** (contenido original, spam, contenido repetitivo). Lo que protege es el ritmo
  bajo, el contenido propio y usar la API oficial.
- **Sin duplicados.** `autopiloto_estado.json` anota lo publicado cada día: si reinicias el programa no repite, y
  `MAX_POSTS_DIA` (2 por defecto) limita el total diario. Un candado (`autopiloto.lock`) impide dos autopilotos a la vez.
- **Errores.** Un fallo del render o de la API se anota en el log y el programa sigue vivo para la siguiente tarea. Los
  fallos temporales (límite de llamadas, errores 5xx de Meta antes de recibir nada) se reintentan hasta `REINTENTOS`
  veces cada `REINTENTO_MIN` minutos **sin volver a renderizar**. Si no se sabe si Meta recibió la publicación (se cortó
  la conexión justo al enviarla), se marca como *ambigua* y **no se reintenta** para no duplicarla: revisa tu página.
- **Reels.** Se sigue la guía oficial: `upload_phase=start`, subida a `rupload.facebook.com` con las cabeceras
  `Authorization: OAuth`, `offset` y `file_size` (un solo cuerpo; si se corta se reanuda desde `bytes_transfered`) y
  `upload_phase=finish` con `video_state=PUBLISHED`. Después espera a que Meta lo procese. Antes de subir se comprueba con
  `ffprobe` que cumple lo que pide Meta (9:16, mínimo 540×960, 24–60 fps, 3–90 s, AAC 48 kHz). Los Reels se envían con
  `is_ai_generated=true` (la voz es sintética) salvo que pongas `IA_ETIQUETA=0`.
- **Fotos.** Se publican con `caption` (el copy) y, si la API lo acepta, `alt_text_custom` (el texto alternativo).
- **Zona horaria y PC.** Las horas son las del PC. Si estuvo apagado o dormido más de `TOLERANCIA_HORAS`, esa tarea del
  día se omite (no se publica de madrugada «para recuperar»).

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

- Los Reels por API tienen un máximo de **30 cada 24 h** (el autopiloto publica 1 al día).
- No cambia la miniatura del Reel, no publica el comentario con la respuesta ni etiqueta las fotos como IA (se dibujan por
  código, no con IA generativa).
- Seguridad: el token no se imprime ni se guarda en el log (se sustituye por `***`). Si crees que se filtró, revócalo desde
  la configuración de tu app y genera otro.
