"""Reservas de texto con *text spinning*: ganchos de apertura, llamadas a seguir, debate en acertijos y fragmentos de
la publicacion. Cada entrada es una plantilla ``{a|b|c}`` (ver `spin.py`) que se expande con el `random.Random` sembrado
del video, de modo que cada semilla produce un guion distinto y la misma semilla lo reproduce exacto.

Todo lo que se dice en voz alta cabe en pocos segundos: ganchos <= 10 palabras, llamadas a seguir <= 10 palabras.
Huecos disponibles: <n> = numero de retos.

Politica de texto (ver `copy_guard.py`, que las pruebas aplican a todo lo generado): ganchos naturales, curiosos y centrados
en resolver el reto. Nada de estadisticas inventadas («el 99 % falla»), de afirmaciones sobre «la mayoria» o «casi nadie»,
ni de peticiones de comentar, compartir, etiquetar, guardar o reaccionar: Meta lo trata como cebo de interaccion y reduce el
alcance. Lo unico que se pide es seguir la pagina, y solo en el cierre del video.
"""
import random

from .spin import pick, spin

# ============================================================================ 1. GANCHOS DE APERTURA (primeros 3-4 s)
# Se narran con la voz Y se queman en pantalla a tamaño grande; el primer reto ya esta visible debajo.
HOOKS_GENERIC = (
    "{Pon a prueba|Entrena|Estira} tu cerebro en {10|15|20} segundos.",
    "{No parpadees|No pestañees|No apartes la vista}: {empieza el reto|esto empieza ya|aquí va el primero}.",
    "{Atento|Concéntrate|Mira bien}: {esto no es tan fácil|esto tiene trampa|esto es más difícil de lo que parece}.",
    "{Tienes 3 segundos|Tienes muy poco tiempo|Solo tienes unos segundos} para {pensar|decidir|acertar}.",
    "<n> retos. {¿Cuántos puedes pasar?|¿Cuántos aciertas?|¿Llegas hasta el final?}",
    "{Mira esto|Mira bien} {con calma|sin pestañear}: {no es lo que parece|hay trampa|algo no cuadra}.",
    "{Prepárate|Prepara tu mente} para {el reto|la prueba} más {traicionero|engañoso|curioso} del día.",
    "{Este reto|Esta prueba} {te va a confundir|te va a enredar la cabeza|te va a hacer dudar}.",
    "{¿Listo?|¿Preparado?|¿Estás listo?|¿Empezamos?}",
    "{Confía en tus ojos|Confía en tu cerebro|Confía en tu intuición}... {si te atreves|si puedes}.",
    "{¿Te crees muy listo?|¿Presumes de buen cerebro?|¿Tienes buena vista?} {Compruébalo|Aquí lo vemos|Ponte a prueba}.",
    "{Tu cerebro|Tu mente} está a punto de {engañarte|jugarte una mala pasada|caer en la trampa}.",
    "{Hoy|Ahora} {te toca|vamos a|vas a} {pensar rápido|mirar bien|usar la cabeza}.",
    "{Un reto nuevo|Una prueba nueva|Un desafío nuevo}: {¿lo resuelves?|¿lo ves?|¿lo sacas?}",
    "{El reto de hoy|El desafío de hoy|La prueba de hoy}: <n> pruebas, {cero errores|ninguna pausa|toda tu atención}.",
    "{Suena fácil|Parece fácil|Parece sencillo}... {pero tiene truco|hasta que lo intentas|¿seguro?}",
    "{Respira hondo|Prepárate|Concéntrate}: {empieza el reto|empezamos ya|esto va a empezar}.",
    "{Ponte cómodo|Súbele al volumen|Mira con atención}, {empieza|arranca|comienza} {el reto|la prueba|el desafío}.",
    "{Te lo advierto|Te aviso|Cuidado}: {el último es el más difícil|el siguiente engaña|esto no es lo que parece}.",
    "{¿Aguantas|¿Resistes|¿Puedes con} <n> retos {sin fallar|sin pausar|sin distraerte}?",
    "{Atención|Ojo|Cuidado|Mira bien|Concentración|Alerta}: {este reto|este nivel|esta prueba|este test} {es peor de lo que parece|no perdona un descuido|tiene trampa|se ríe de tu cerebro}.",
    "{Prohibido|Ni se te ocurra} {parpadear|pausar|apartar la vista|mirar la respuesta}: {esto va rápido|empieza ya|vamos allá}.",
    "{Si dudas en el primero|Si fallas el primero|Si te despistas}, {el siguiente será peor|prepárate para el segundo|ojo con el último}.",
    "{Hoy toca|Esto es} {un reto de|una prueba de} {lógica|atención|memoria|observación} {con truco|con trampa|sin pausas}.",
    "{¿Ves la trampa?|¿Dónde está el truco?|¿Qué esconde este reto?} {Míralo bien|Con calma|Sin prisa}.",
    "{Tu cerebro|Tu atención|Tu vista} contra <n> retos. {¿Quién gana?|Que empiece el juego.|¿Listo?}",
    "{Reto de lógica|Reto de atención|Reto visual|Reto mental}: <n> pruebas con solución al final.",
    "{Mira bien|Observa con calma|Fíjate en cada detalle}: {la respuesta está a la vista|todo está ahí|nada es casual}.",
    "{¿Puedes con esto?|¿Y si lo intentas?|¿Te animas?} {Es más difícil de lo que parece|Tiene truco|Sin pausar el video}.",
    "{Piénsalo dos veces|Piensa antes de responder|Tómate tu tiempo}: {la primera idea no siempre es la correcta|hay trampa|las apariencias engañan}.",
    "{Un reto rápido|Una prueba rápida|Un minuto de reto}: {mira bien|piensa con calma|usa la cabeza}.",
    "{Hoy traigo|Hoy toca|Hoy vamos con} <n> {retos|pruebas|desafíos} {con truco|con trampa|de ingenio}.",
    "{Este reto|Esta prueba|Este nivel} {parece fácil|parece sencillo|parece tonto}... {pero no lo es|pero ten cuidado|pero tiene truco}.",
    "{Antes de responder|Antes de decidir|Antes de apostar}, {piensa dos veces|mira con calma|respira hondo}.",
    "{Mira|Observa|Fíjate} {bien|con calma|sin prisa} y {responde|decide|elige} {antes de la solución|con cuidado|sin trampa}.",
    "{¿Qué ves?|¿Qué notas?|¿Qué descubres?} {Míralo bien|Mira con calma|Mira dos veces}.",
)
HOOKS_BY_CATEGORY = {
    "Visual": (
        "{Tus ojos|Tu vista} te van a {jugar una mala pasada|engañar|traicionar}.",
        "{¿Presumes de|¿Tienes} {vista de águila|buena vista|ojo de halcón}? {Compruébalo|Ponte a prueba}.",
        "{Encuentra|Localiza} lo que {no encaja|está fuera de lugar} a tiempo.",
        "{Lo que ves|Lo que crees ver} {no siempre es real|puede ser un engaño|no es lo que parece}.",
    ),
    "Mente": (
        "{¿Eres más listo que|¿Le ganas a} {este acertijo|esta pregunta trampa|este reto de lógica}? {Demuéstralo|Resuélvelo}.",
        "{Piensa dos veces|Piénsalo bien}: {la primera respuesta no siempre es la correcta|tu primera idea puede fallar}.",
        "{Un reto de lógica|Una pregunta con truco}: {tómate tu tiempo|piénsalo con calma|sin calculadora y sin prisa}.",
    ),
    "Atención": (
        "Un {descuido|parpadeo|segundo de distracción} y {fallas|pierdes|te lo pierdes}.",
        "{Mantén los ojos fijos|Concentra la vista|Presta mucha atención}: {esto se mueve rápido|no te perdonará nada|va a ser rápido}.",
    ),
    "Memoria": (
        "{¿Tienes|¿Presumes de} {buena memoria|memoria de elefante}? {Compruébalo|Demuéstralo} {ahora|ya}.",
        "{Memoriza|Fíjate bien en|Graba en tu mente} todo lo que veas: {luego|después} {te preguntaré|vendrá la trampa}.",
    ),
    "Reflejos": (
        "{Un solo fotograma|Solo un instante|Una fracción de segundo} {decide|define} si {ganas|aciertas}.",
        "¿Tus reflejos son tan buenos como crees? {Demuéstralo|Vamos a ver}.",
    ),
}
HOOKS_LOOP = (
    "{Este video es un bucle perfecto|Este bucle no tiene principio ni final|Esto nunca termina}. {¿Puedes ver dónde empieza?|¿Puedes ver dónde termina?|Intenta encontrar el inicio.|Intenta encontrar el final.}",
    "{Mira fijamente|No apartes la vista|Quédate mirando}. {Esto nunca termina|Esto no tiene final|Esto no tiene principio}.",
    "{¿Dónde empieza|¿Dónde termina} este {bucle|video|movimiento}? {Míralo con calma|Inténtalo|Fíjate bien}.",
)

HOOKS_LOOP += (
    "{Mira|Observa|Fíjate en} este {bucle|movimiento|giro}: {nunca termina|no tiene final|no tiene principio}.",
    "{Intenta|Prueba a} {encontrar|ver} {el principio|el final|el empalme} de este {bucle|video}.",
    "{Relájate|Respira hondo|Ponte cómodo}: {este bucle|este video} {no se acaba|es infinito|no termina nunca}.",
    "{Intenta|Prueba a} {apartar la vista|dejar de mirar|no mirar}. {Cuesta más de lo que parece|Es hipnótico|Es más difícil de lo que crees}.",
    "{Este video|Este bucle} {te va a hipnotizar|te va a atrapar|no te va a soltar}. {Mira fijamente|No apartes la vista|Quédate mirando}.",
)

# ============================================================================ 2. LLAMADAS A SEGUIR (ultimos 4-5 s)
# Se narran Y se queman en pantalla. Solo piden seguir la pagina: sin comentar, compartir ni etiquetar, sin premios ni
# promesas que no se cumplan y sin afirmar nada sobre lo que hace «la mayoria».
CTAS = (
    "{¿Perdiste?|¿Fallaste?|¿Te equivocaste?|¿Te ganó el reto?} Sígueme para tu {revancha|desquite} {mañana|en el próximo video}.",
    "{¿Te engañó tu mente?|¿Te engañaron tus ojos?|¿Casi lo logras?} Sígueme para el nivel {2|siguiente|más difícil}.",
    "{Sígueme y no te pierdas|Sígueme para ver|Sígueme y descubre} el reto de mañana.",
    "{Cada día|Todos los días} {un reto nuevo|un desafío distinto}. Sígueme {y entrena tu mente|para no perdértelo|para jugar mañana}.",
    "{¿Quieres un nivel más difícil?|¿Te atreves con algo peor?|¿Quieres otro reto?} Sígueme.",
    "Sígueme: mañana el reto {es peor|es más difícil|viene con trampa|no será tan fácil}.",
    "{¿Cuántos acertaste?|¿Hasta dónde llegaste?|¿Cuántas pruebas lograste?} Sígueme para {la revancha|el siguiente|más retos}.",
    "{Si te costó|Si te gustó|Si te sorprendió}, sígueme: mañana hay {otro reto|más|revancha}.",
    "Esto fue solo el {calentamiento|principio|nivel básico}. Sígueme para el siguiente.",
    "{No te vayas sin seguirme|Sígueme ahora}: {mañana|pronto} hay {revancha|un desafío nuevo|otro nivel}.",
    "Sígueme y {entrena|desafía|pon a prueba} tu mente {todos los días|cada mañana|cada día}.",
    "{Mañana|Pronto} {te toca algo peor|vuelvo con otro reto|traigo un nivel más difícil}. Sígueme.",
    "{Sigue la cuenta|Sígueme} y {no te pierdas|mira} el siguiente {reto|nivel|desafío}.",
    "{¿Quieres la revancha?|¿Quieres tu revancha?} Sígueme y {mañana|pronto} la tienes.",
)
CTAS += (
    "{¿Fallaste?|¿Acertaste?|¿Lo lograste?} {Sígueme|Sígueme ya|Sígueme ahora} y {mañana|pronto} {te toca otro|vienes por más|hay nivel nuevo}.",
    "{Un reto nuevo cada día|Retos nuevos todos los días|Más pruebas mañana}: {sígueme|sigue la cuenta|sígueme para verlos}.",
    "{Si llegaste hasta aquí|Si aguantaste hasta el final|Si no pausaste}, {bien hecho|buen trabajo|vas muy bien}. Sígueme para el siguiente.",
    "{¿Quieres más retos así?|¿Te gustó el reto?|¿Te quedaste con ganas de más?} {Sígueme|Sígueme y lo tienes|Sígueme y mañana hay otro}.",
    "{Mañana|Pronto} {pongo|traigo|subo} {un reto más difícil|otra prueba|otro nivel}. {Sígueme para no perdértelo|Sígueme}.",
    "{Hoy fue el reto|Esto fue el reto} de hoy. {Sígueme para el de mañana|Sígueme y vuelve mañana|Mañana hay otro: sígueme}.",
    "{Sígueme|Sigue la cuenta} {para más retos|para más pruebas|para más desafíos} {como este|cada día|todas las semanas}.",
    "{¿Listo para el siguiente?|¿Preparado para el próximo?|¿Quieres el próximo reto?} Sígueme y {mañana|pronto} lo ves.",
    "{Entrena tu cerebro|Entrena tu atención|Entrena tu memoria} {cada día|todos los días|cada mañana}: sígueme.",
    "{Fue divertido|Ha sido un buen reto|Gracias por jugar}. {Sígueme para el siguiente|Sígueme y vuelve mañana|Sígueme para más}.",
    "{Un reto más|Otro reto más|Una prueba más} {terminado|completado}. Sígueme para {el siguiente|el de mañana|más}.",
    "{¿Te gustan los retos?|¿Te gustan los acertijos?|¿Te gusta pensar?} {Sígueme|Sigue la cuenta} y {juega|piensa|compite} {mañana|cada día}.",
)

CTAS_LOOP = (
    "{¿Cuántas veces lo viste?|¿Lo encontraste?|¿Viste dónde empieza?} Sígueme para {otro bucle|más videos hipnóticos|el de mañana}.",
    "{Sigue mirando|Sigue en bucle}, pero antes sígueme: {mañana|pronto} hay {otro|uno nuevo}.",
    "{Si te hipnotizó|Si te quedaste mirando|Si no pudiste dejar de mirar}, sígueme: {mañana|pronto} viene {otro|uno distinto}.",
    "{Cada día|Todos los días} {un bucle nuevo|un video distinto}. Sígueme {y relájate|para no perdértelo|para verlo mañana}.",
    "{Sígueme y no te pierdas|Sígueme para ver|Sígueme y descubre} {el próximo bucle|el de mañana|otro igual de hipnótico}.",
    "{Sigue la cuenta|Sígueme} y {mira|no te pierdas} el siguiente {bucle|video}.",
)

# ============================================================================ 3. DEBATE EN ACERTIJOS Y CALCULO
# Con trampa conocida (la respuesta intuitiva): <trap> y <ans>. Solo se afirma lo que es cierto: nada de «la mayoria dice».
DEBATE_TRAP = (
    "{La respuesta rápida es|El instinto dice|Tu primera idea fue|Lo primero que sale es} <trap>, pero {es|la correcta es} <ans>. {¿Cuál elegiste?|¿Caíste?|¿Y tú?|¿Lo viste venir?}",
    "<trap> {es la respuesta tentadora|es la trampa|es lo primero que se piensa}, pero {es|resulta ser} <ans>. {¿Cuál dijiste?|¿Caíste?|¿Lo viste venir?}",
    "{Ojo|Cuidado}: <trap> {es la trampa|no es la respuesta}. {Es|La correcta es} <ans>. {¿Caíste?|¿Y tú?|¿Lo viste venir?}",
)
DEBATE_TRAP_SCREEN = ("{EL INSTINTO DICE|LA RESPUESTA RÁPIDA|LA TRAMPA ES|ES TENTADOR DECIR} <trap>",)
# Sin trampa conocida: se pregunta por la respuesta del espectador, sin inventar porcentajes.
DEBATE_PLAIN = ("<ans> {¿Lo acertaste?|¿Y tú qué dijiste?|¿Coincide con tu respuesta?|¿Lo sacaste?}",
                "<ans> {¿Era la tuya?|¿Lo viste venir?|¿Te engañó?|¿Lo tenías claro?}",
                "{La respuesta es|Respuesta:|Solución:} <ans_l>. {¿Lo sacaste a la primera?|¿Lo habías pensado?|¿Coincide con la tuya?}",
                "<ans> {Si dudaste, es normal.|Tiene truco, ¿verdad?|No era tan fácil.} {¿Tú qué opinas?|¿Y tú?}")
DEBATE_PLAIN_SCREEN = ("{¿Y TÚ QUÉ DIJISTE?|¿LO ACERTASTE?|¿COINCIDE CON TU RESPUESTA?|¿CUÁL ELEGISTE?|¿LO SACASTE?}",)
# Linea corta antes de la solucion (<= 4 palabras: cabe en 2 s)
DEBATE_PRE = ("{Piénsalo bien|Tómate tu tiempo|No mires la solución|Piensa tu respuesta}.",
              "{¿Seguro que es fácil?|¿Ya lo sabes?|¿Tienes tu respuesta?}")

# ============================================================================ 4. FRAGMENTOS DE LA PUBLICACION
TITLE_OPEN = ("Parece fácil", "Tiene truco", "Cuidado con la trampa", "Nivel difícil", "Reto del día", "Prueba de fuego",
              "Piénsalo dos veces", "Esto engaña a la vista", "No es tan fácil", "Mira con calma", "Un reto con truco",
              "Pon a prueba tu cerebro")
TITLE_CLOSE = ("¿Y tú?", "¿Lo logras?", "Demuéstralo.", "Compruébalo.", "¿Te atreves?", "Respuesta al final.", "Sin trampas.",
               "¿Cuántos aciertas?")
# Esqueletos de titulo: <open>/<open_l> (con mayuscula inicial o sin ella), <close>, <act> (infinitivo), <plural>, <n>
TITLE_FRAMES = (
    "<open>: ¿puedes <act>? <close>",
    "¿Puedes <act>? <open>. <close>",
    "<n> <plural>: <open_l>. <close>",
    "<open> en estos <n> <plural>. <close>",
    "<n> <plural> y {una sola oportunidad|ni una pausa|cero trampas}. <close>",
)
# Primera linea de la descripcion cuando no se usa la propia del tipo de reto
DESC_OPEN = (
    "<n> <plural> para {poner a prueba|entrenar|retar a} {tu cerebro|tu mente|tu atención}. <emo>",
    "{Hoy traigo|Nuevo video:|Hoy toca} <n> <plural>. {¿Podrás con todos?|¿Cuántos sacas?|Sin hacer pausas.} <emo>",
    "{Un reto|Una prueba|Un desafío} {con truco|con trampa|de ingenio}: <act> en estos <n> <plural>. <emo>",
    "{Mira con calma|Mira bien|Atento}: <n> <plural> y {una trampa en cada uno|más dificultad en cada uno|la respuesta al final}. <emo>",
)
EMOJIS = ("🧠", "👀", "⚡", "🔥", "🎯", "⏱️", "🤔")
# Cierre de la descripcion: una pregunta o una indicacion sobre el propio reto; nunca pide comentar, compartir ni etiquetar.
COMMENT_ASK = (
    "{¿Cuántos de los <n> retos lograste resolver?|¿Cuántos de los <n> retos acertaste?|¿Cuántos de los <n> retos resuelves sin pausar?}",
    "{¿Qué reto te costó más?|¿Cuál fue tu reto favorito?|¿En cuál dudaste?} {La solución de cada uno llega al final.|Todos tienen solución.}",
    "{¿Cuál de los <n> retos te pareció el más difícil?|¿Qué reto te engañó más?}",
    "{Piensa tu respuesta antes de ver la solución|Tómate tu tiempo en cada reto}. La solución llega al final de cada uno.",
)
COMMENT_ASK_LOOP = (
    "¿Cuántas veces {lo repetiste|lo viste}?",
    "¿En qué segundo {creíste ver el principio|notaste el empalme}?",
)
# Linea final neutra de la publicacion (en lugar de pedir compartir o seguir).
CLOSERS = (
    "{Retos de lógica y atención|Retos mentales cortos|Entrenamiento mental en pocos segundos|Un reto para cada día} en esta página.",
    "{Mira con calma|Tómate tu tiempo|Sin prisa y sin trampas}: la solución llega al final.",
    "{Un minuto para pensar|Un rato para entrenar la mente|Un reto corto para tu día}.",
)
SEO_TAIL = ("{Perfecto para entrenar la mente|Ideal para jugar con amigos|Un reto rápido para tu día|Ejercita tu cerebro en un minuto|Para ver con calma y sin trampas}.",)

TAG_POOLS = {
    "anomaly": ("#RetoVisual", "#EncuentraLaDiferencia", "#TestVisual", "#TestDeAtencion", "#JuegosMentales", "#BuscaLaDiferencia", "#EntrenaTuMente"),
    "illusion": ("#IlusionOptica", "#IlusionesOpticas", "#TuCerebroTeEngana", "#TrucosVisuales", "#TrucoVisual", "#Percepcion", "#CuriosidadesVisuales"),
    "ishihara": ("#TestDeVision", "#Ishihara", "#PruebaVisual", "#RetoVisual", "#TestDeColores", "#VistaDeAguila", "#JuegosMentales"),
    "magiceye": ("#OjoMagico", "#Autoestereograma", "#Imagen3D", "#RetoVisual", "#Estereograma", "#EnfocaLaVista", "#IlusionOptica"),
    "contrast": ("#IlusionOptica", "#ContrasteSimultaneo", "#TuCerebroTeEngana", "#IlusionesDeColor", "#TrucoVisual", "#Percepcion"),
    "sync": ("#RetoDeReflejos", "#PausaElVideo", "#RetoVisual", "#TiempoDeReaccion", "#TestDeReflejos", "#JuegosMentales"),
    "swarm": ("#RetoDeAtencion", "#SigueElPunto", "#RetoVisual", "#TestDeAtencion", "#SeguimientoVisual", "#JuegosMentales"),
    "count": ("#CuentaLasFiguras", "#RetoDeAtencion", "#RetoVisual", "#TestDeConcentracion", "#JuegosMentales", "#EntrenaTuMente"),
    "flicker": ("#QueCambio", "#RetoDeAtencion", "#RetoVisual", "#DetectaElCambio", "#TestDeAtencion", "#BuscaLaDiferencia"),
    "memory": ("#TestDeMemoria", "#Memoria", "#RetoMental", "#EntrenaTuMemoria", "#MemoriaVisual", "#JuegosMentales"),
    "stroop": ("#EfectoStroop", "#RetoMental", "#TuCerebro", "#TestDeColores", "#Psicologia", "#JuegosMentales"),
    "math": ("#RetoMatematico", "#Matematicas", "#RetoMental", "#CalculoMental", "#AcertijosMatematicos", "#TestDeLogica"),
    "sequence": ("#QueNumeroSigue", "#RetoDeLogica", "#Matematicas", "#SeriesNumericas", "#TestDeLogica", "#RetoMental"),
    "riddle": ("#Acertijos", "#Adivinanzas", "#RetoMental", "#AcertijosConRespuesta", "#PreguntasTrampa", "#TestDeLogica", "#JuegosMentales"),
    "cups": ("#JuegoDeLosVasos", "#SigueLaBola", "#RetoDeAtencion", "#RetoVisual", "#DondeEstaLaBola", "#JuegosMentales"),
    "simon": ("#Simon", "#TestDeMemoria", "#RetoMental", "#Memoria", "#MemoriaDeTrabajo", "#JuegosMentales"),
    "digits": ("#EncuentraElNumero", "#TestVisual", "#RetoVisual", "#EncuentraLaDiferencia", "#TestDeAtencion", "#VistaDeAguila"),
    "loop": ("#BucleInfinito", "#PerfectLoop", "#Hipnotico", "#Satisfying", "#VideosRelajantes", "#Loop"),
    "mix": ("#RetoMental", "#TestDeCerebro", "#RetoVisual", "#JuegosMentales", "#TestDeAtencion", "#EntrenaTuMente", "#TestDeMemoria"),
}


# ============================================================================ funciones de eleccion
def make_hook(rng: random.Random, category: str | None, n: int | str, loop: bool = False) -> str:
    """Gancho de apertura: pool generico + el de la categoria del reto (un video mixto usa solo el generico)."""
    pool = HOOKS_LOOP if loop else HOOKS_GENERIC + HOOKS_BY_CATEGORY.get(category or "", ())
    return pick(rng, pool, n=n)


def hook_lead(hook: str) -> float:
    """Segundos de apertura (el reto esta quieto y visible mientras suena el gancho): voz a ritmo natural + margen."""
    return round(min(4.4, max(2.5, 0.42 * len(hook.split()) + 0.6)), 2)      # la voz tarda ~0,43 s por palabra


def make_cta(rng: random.Random, loop: bool = False) -> str:
    return pick(rng, CTAS_LOOP if loop else CTAS)


def lc_first(text: str) -> str:
    """Minuscula inicial y sin punto final, para incrustar una respuesta dentro de una frase."""
    text = text.strip().rstrip(".")
    return text[:1].lower() + text[1:]


def make_debate(rng: random.Random, ans: str, trap: str | None, max_words: int | None = None) -> str:
    """Narracion de la revelacion: con trampa conocida enfrenta la respuesta comun con la correcta; si no, pide la tuya.
    Con `max_words` se prueban varias variantes y se elige una que quepa en el hueco de voz (o la mas corta)."""
    ans = ans.strip()
    plain = ans if ans[-1:] in (".", "!", "?") else ans + "."

    def one() -> str:
        if trap:
            return spin(rng, rng.choice(DEBATE_TRAP), ans=lc_first(ans), trap=lc_first(trap))
        return spin(rng, rng.choice(DEBATE_PLAIN), ans=plain, ans_l=lc_first(plain))

    if not max_words:
        return one()
    lines = [one() for _ in range(8)]
    return next((x for x in lines if len(x.split()) <= max_words), min(lines, key=lambda x: len(x.split())))


def make_debate_screen(rng: random.Random, trap: str | None) -> str:
    """Ficha que se quema durante la revelacion (mayusculas, corta: cabe en una o dos lineas)."""
    if trap:
        return spin(rng, rng.choice(DEBATE_TRAP_SCREEN), trap=trap.strip().rstrip(".").upper())
    return spin(rng, rng.choice(DEBATE_PLAIN_SCREEN))


def make_debate_pre(rng: random.Random) -> str:
    """Linea corta justo antes de revelar, para que el espectador escriba su respuesta."""
    return spin(rng, rng.choice(DEBATE_PRE))


# ============================================================================ piezas de la publicacion
BRAND_TAG = "#ParadojaInfinita"


def make_title(rng: random.Random, act: str, plural: str, n: int) -> str:
    """Titulo armado con fragmentos: esqueleto + frase de apertura + cierre."""
    op = rng.choice(TITLE_OPEN)
    return spin(rng, rng.choice(TITLE_FRAMES), open=op, open_l=lc_first(op), close=rng.choice(TITLE_CLOSE),
                act=act, plural=plural, n=n)


def make_desc_open(rng: random.Random, act: str, plural: str, n: int) -> str:
    return spin(rng, rng.choice(DESC_OPEN), act=act, plural=plural, n=n, emo=rng.choice(EMOJIS))


def make_ask(rng: random.Random, n: int, loop: bool = False) -> str:
    return pick(rng, COMMENT_ASK_LOOP if loop else COMMENT_ASK, n=n)


def make_closer(rng: random.Random) -> str:
    """Linea final neutra de la publicacion (no pide compartir, seguir ni comentar)."""
    return pick(rng, CLOSERS)


def make_seo_tail(rng: random.Random) -> str:
    return pick(rng, SEO_TAIL)


def make_tags(rng: random.Random, mode: str, types=()) -> list:
    """Hasta 4 etiquetas del tipo (3 o 4 al azar, en orden aleatorio) + la marca al final: nunca mas de 5 (guia de Meta)."""
    pool = list(TAG_POOLS[mode])
    if mode == "mix":                                   # etiquetas de los tipos que aparecen en el video
        own = [TAG_POOLS[t][0] for t in dict.fromkeys(types) if t in TAG_POOLS]
        tags = rng.sample(pool, 2) + rng.sample(own, min(2, len(own)))
    else:
        tags = rng.sample(pool, min(rng.choice((3, 4)), len(pool)))
    return list(dict.fromkeys(tags))[:4] + [BRAND_TAG]


PINNED = (
    "{La solución de cada uno de los <n> retos aparece al final.|Los <n> retos tienen su solución al final de cada uno.|Cada reto muestra su solución al terminar.} {Míralo con calma.|Sin pausar y sin trampas.|Tómate tu tiempo.}",
    "{Pista|Consejo}: {tómate tu tiempo en cada reto|piensa tu respuesta antes de ver la solución|no te precipites con la primera idea}. Hay <n> retos.",
)
PINNED_LOOP = (
    "{Este bucle no tiene principio ni final.|El final conecta con el principio sin saltos.|Es un bucle perfecto: no hay corte.}",
)


def make_pinned(rng: random.Random, n: int, loop: bool = False) -> str:
    """Nota sugerida para fijar en los comentarios: informa, no pide nada."""
    return pick(rng, PINNED_LOOP if loop else PINNED, n=n)
