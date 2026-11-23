"""Reservas de texto con *text spinning*: ganchos de apertura, llamadas a seguir, debate en acertijos y fragmentos de
la publicacion. Cada entrada es una plantilla ``{a|b|c}`` (ver `spin.py`) que se expande con el `random.Random` sembrado
del video, de modo que cada semilla produce un guion distinto y la misma semilla lo reproduce exacto.

Todo lo que se dice en voz alta cabe en pocos segundos: ganchos <= 10 palabras, llamadas a seguir <= 10 palabras.
Huecos disponibles: <n> = numero de retos.
"""
import random

from .spin import pick, spin

# ============================================================================ 1. GANCHOS DE APERTURA (primeros 3-4 s)
# Se narran con la voz Y se queman en pantalla a tamaño grande; el primer reto ya esta visible debajo.
HOOKS_GENERIC = (
    "{El|Más del} {90|95|97|99}% de las personas falla {este nivel|este reto|esta prueba}.",
    "Solo si tienes {un IQ alto|buena vista|mucha paciencia|una mente rápida} podrás {resolver esto|pasar este nivel|con este reto}.",
    "{No parpadees|No pestañees|No apartes la vista} o {perderás el juego|perderás este reto|fallarás}.",
    "Te apuesto a que no puedes {encontrar el error|resolverlo|verlo a la primera|acertar el último}.",
    "Pon a prueba tu cerebro en {10|15} segundos.",
    "{Casi nadie|Muy poca gente|Poquísima gente} pasa {este nivel|este test|este reto}.",
    "{¿Te crees muy listo?|¿Te crees un genio?|¿Presumes de buen cerebro?} {Demuéstralo|Compruébalo|Aquí lo vemos}.",
    "{Tu cerebro|Tu mente} está a punto de {engañarte|traicionarte|mentirte}.",
    "{Atento|Concéntrate|Mira bien}: {esto no es tan fácil|esto tiene trampa|esto es más difícil de lo que parece}.",
    "{Tienes 3 segundos|Tienes muy poco tiempo|Solo tienes unos segundos} para {pensar|decidir|acertar}.",
    "{Te reto|Te desafío|Te apuesto algo} a que {fallas|te equivocas|no lo logras}.",
    "Si aciertas {los <n>|todos}, {eres un genio|eres de los pocos|eres especial}.",
    "{Nadie|Casi nadie} acierta {el último|el reto final|el nivel final}.",
    "<n> retos. {¿Cuántos puedes pasar?|¿Cuántos aciertas?|¿Llegas hasta el final?}",
    "{Mira esto|Mira bien} {con calma|sin pestañear}: {no es lo que parece|hay trampa|algo no cuadra}.",
    "{Prepárate|Prepara tu mente} para {el reto|la prueba} más {traicionero|engañoso|cruel} del día.",
    "{Este video|Este reto} {te va a confundir|te va a enredar la cabeza|te va a hacer dudar}.",
    "{¿Listo?|¿Preparado?|¿Estás listo?|¿Listo para fallar?}",
    "{Confía en tus ojos|Confía en tu cerebro|Confía en tu intuición}... si te atreves.",
    "{Solo los atentos|Solo los pacientes|Solo los más listos} {lo logran|pasan este nivel|lo resuelven}.",
    "{Nadie se libra|Muy pocos se libran|Casi nadie se salva} de {este truco|esta trampa|este engaño}.",
    "{Ojo|Cuidado}: {este reto|este nivel} {ha hecho fallar a muchos|no perdona|tiene truco}.",
)
HOOKS_GENERIC += (
    "{Atención|Ojo|Cuidado|Mira bien|Concentración|Alerta|Ponte serio}: {este reto|este nivel|esta prueba|este test} {es peor de lo que parece|ha hecho fallar a muchos|no perdona un descuido|se ríe de tu cerebro|tiene trampa}.",
    "{Esto|Este reto|Este nivel} lo {resuelve|supera|pasa} {1 de cada 10|1 de cada 20|1 de cada 50|muy poca gente}. {¿Serás tú?|¿Te atreves?|¿Eres tú?}",
    "{Prohibido|Ni se te ocurra} {parpadear|pausar|apartar la vista|mirar la respuesta}: {esto va rápido|empieza ya|vamos allá}.",
    "{Si fallas el primero|Si dudas en el primero|Si te equivocas en el primero}, {no llegas al último|se acabó el juego|pierdes}.",
    "{¿Crees que es fácil?|¿Te parece sencillo?|¿Crees que lo tienes controlado?} {Espera y verás|Mira esto|Ya veremos}.",
    "{El reto de hoy|El desafío de hoy|La prueba de hoy}: <n> pruebas, {cero errores|ninguna pausa|toda tu atención}.",
    "{Suena fácil|Parece fácil|Parece imposible}... {pero no lo es|hasta que lo intentas|pero tiene truco}.",
    "{Concéntrate|Respira hondo|Prepárate}: {empieza el reto|empezamos ya|esto va a empezar}.",
    "{Nadie|Casi nadie|Muy pocos} {lo logra|acierta|llega al final} {sin fallar|sin pausar|a la primera}.",
    "{Hoy|Ahora} {te toca|te reto a|vas a} {pensar rápido|mirar bien|usar la cabeza}.",
    "{Solo los más atentos|Solo los más rápidos|Solo los más listos} {llegan al final|ven la respuesta|aciertan los <n>}.",
    "{¿Sabes|¿Seguro que sabes|¿Crees que sabes} {mirar|pensar|concentrarte} de verdad? {Compruébalo|Aquí lo vemos|Ahora}.",
    "{Tu cerebro|Tu mente|Tu atención} contra <n> retos. {¿Quién gana?|¿Quién se rinde primero?|Que empiece el juego.}",
    "{Te lo advierto|Te aviso|Cuidado}: {el último es el peor|el siguiente engaña|esto no es lo que parece}.",
    "{Ponte cómodo|Súbele al volumen|Mira con atención}, {empieza|arranca|comienza} {el nivel difícil|la prueba|el desafío}.",
    "{¿Aguantas|¿Resistes|¿Sobrevives a} <n> retos {sin fallar|sin pausar|sin distraerte}?",
)
HOOKS_BY_CATEGORY = {
    "Visual": (
        "{Tus ojos|Tu vista} te van a {mentir|engañar|traicionar}.",
        "{¿Presumes de|¿Tienes} {vista de águila|buena vista|ojo de halcón}? {Demuéstralo|Compruébalo}.",
        "{Encuentra|Localiza} lo que {no encaja|está fuera de lugar} a tiempo.",
        "{Lo que ves|Lo que crees ver} {no es real|es un engaño|no es lo que parece}.",
    ),
    "Mente": (
        "{¿Eres más listo que|¿Le ganas a} {tus amigos|tu familia|la mayoría}? {Demuéstralo|Resuelve esto}.",
        "{Piensa dos veces|Piénsalo bien}: {la primera respuesta suele ser la incorrecta|tu primera idea suele fallar}.",
        "{Solo un genio resuelve|Solo alguien muy listo resuelve|Muy pocos resuelven} esto sin {calculadora|pensar mucho|dudar}.",
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
    "{¿Dónde empieza|¿Dónde termina} este {bucle|video|movimiento}? {Casi nadie lo sabe|Nadie lo encuentra|Inténtalo}.",
)

HOOKS_LOOP += (
    "{Mira|Observa|Fíjate en} este {bucle|movimiento|giro}: {nunca termina|no tiene final|no tiene principio}.",
    "{Nadie|Casi nadie|Muy poca gente} {encuentra|ve|nota} {el principio|el final|el empalme} de este {bucle|video}.",
    "{Relájate|Respira hondo|Ponte cómodo}: {este bucle|este video} {no se acaba|es infinito|no termina nunca}.",
    "{Intenta|Prueba a} {apartar la vista|dejar de mirar|no mirar}. {No podrás|Es imposible|Casi nadie puede}.",
    "{Este video|Este bucle} {te va a hipnotizar|te va a atrapar|no te va a soltar}. {Mira fijamente|No apartes la vista|Quédate mirando}.",
)

# ============================================================================ 2. LLAMADAS A SEGUIR (ultimos 4-5 s)
# Se narran Y se queman en pantalla. Todas piden seguir la cuenta; sin premios ni promesas que no se cumplan.
CTAS = (
    "{¿Perdiste?|¿Fallaste?|¿Te equivocaste?|¿Te ganó el reto?} Sígueme para tu {revancha|desquite} {mañana|en el próximo video}.",
    "Si lo {lograste|resolviste|acertaste}, sígueme y {comenta tu tiempo|cuéntame cómo te fue|comenta tu nota}.",
    "{Únete al 1% que gana|Únete al club de los que aciertan|Súmate a los que siempre resuelven}. Sígueme para más retos.",
    "{¿Te engañó tu mente?|¿Te engañaron tus ojos?|¿Casi lo logras?} Sígueme para el nivel {2|siguiente|más difícil}.",
    "{Sígueme y no te pierdas|Sígueme para ver|Sígueme y descubre} el reto de mañana.",
    "{Cada día|Todos los días} {un reto nuevo|un desafío distinto}. Sígueme {y entrena tu mente|para no perdértelo|para jugar mañana}.",
    "{Demuestra que no fue suerte|Demuestra que eres de los pocos|Demuestra que lo tuyo es real}: sígueme y {vuelve mañana|juega mañana|intenta el siguiente}.",
    "{¿Quieres un nivel más difícil?|¿Te atreves con algo peor?|¿Quieres otro reto?} Sígueme.",
    "Sígueme: mañana el reto {es peor|es más difícil|viene con trampa|no será tan fácil}.",
    "Guarda este video y sígueme para {más retos|nuevos desafíos|la revancha}.",
    "¿{Cuántos acertaste|Cuántas pruebas lograste|Hasta dónde llegaste}? Sígueme y comenta tu {nota|puntaje|resultado}.",
    "{Si te costó|Si te gustó|Si te sorprendió}, sígueme: mañana hay {otro reto|más|revancha}.",
    "Esto fue solo el {calentamiento|principio|nivel básico}. Sígueme para el siguiente.",
    "{No te vayas sin seguirme|Sígueme ahora}: {mañana|pronto} hay {revancha|un desafío nuevo|otro nivel}.",
    "¿{Eres de los pocos que ganan|Eres de los que no fallan|Eres de los que aciertan a la primera}? Sígueme y {demuéstralo|compruébalo} mañana.",
    "Sígueme y {entrena|desafía|pon a prueba} tu mente {todos los días|cada mañana|cada día}.",
    "{Mañana|Pronto} {te toca algo peor|vuelvo con otro reto|traigo un nivel más difícil}. Sígueme.",
    "{Dale a seguir|Pulsa seguir|Sigue la cuenta} y {no te pierdas|mira} el siguiente {reto|nivel|desafío}.",
    "{¿Quieres la revancha?|¿Quieres tu revancha?} Sígueme y {mañana|pronto} la tienes.",
)
CTAS += (
    "{¿Fallaste?|¿Acertaste?|¿Lo lograste?} {Sígueme|Sígueme ya|Sígueme ahora} y {mañana|pronto} {te toca otro|vienes por más|hay nivel nuevo}.",
    "{Un reto nuevo cada día|Retos nuevos todos los días|Más pruebas mañana}: {sígueme|dale a seguir|sígueme para verlos}.",
    "{Si llegaste hasta aquí|Si aguantaste hasta el final|Si no pausaste}, {eres de los pocos|mereces más|vas bien}. Sígueme para el siguiente.",
    "{¿Quieres más retos así?|¿Te gustó el reto?|¿Te quedaste con ganas de más?} {Sígueme|Sígueme y lo tienes|Sígueme y mañana hay otro}.",
    "{Mañana|Pronto} {pongo|traigo|subo} {un reto más difícil|otra prueba|otro nivel}. {Sígueme para no perdértelo|Sígueme|Sígueme y compite}.",
    "{Compártelo|Mándaselo a un amigo} y {sígueme|sígueme para más}: {mañana hay revancha|hay más retos cada día|el siguiente es peor}.",
)

CTAS_LOOP = (
    "{¿Cuántas veces lo repetiste?|¿Cuántas veces lo viste?} Sígueme para {otro bucle|más videos hipnóticos|el de mañana}.",
    "{Sigue mirando|Sigue en bucle}, pero antes sígueme: {mañana|pronto} hay {otro|uno nuevo}.",
    "{¿Lo encontraste?|¿Viste dónde empieza?|¿Viste el empalme?} Sígueme y {cuéntame|comenta} cuántas veces lo viste.",
    "{Si no pudiste dejar de mirar|Si te hipnotizó|Si te quedaste mirando}, sígueme: {mañana|pronto} viene {otro|uno distinto}.",
    "{Cada día|Todos los días} {un bucle nuevo|un video distinto}. Sígueme {y relájate|para no perdértelo|para verlo mañana}.",
    "{Sígueme y no te pierdas|Sígueme para ver|Sígueme y descubre} {el próximo bucle|el de mañana|otro igual de hipnótico}.",
    "{Dale a seguir|Pulsa seguir|Sigue la cuenta} y {mira|no te pierdas} el siguiente {bucle|video}.",
)

# ============================================================================ 3. DEBATE EN ACERTIJOS Y CALCULO
# Con trampa conocida (la respuesta intuitiva que casi todos dan): <trap> y <ans>. Solo se afirma lo que es cierto.
DEBATE_TRAP = (
    "{Muchos dicen|Mucha gente responde|Casi todos dicen|La mayoría responde} <trap>, pero es <ans>. {¿Y tú qué dijiste?|¿Tú qué opinas?|¿Estás de acuerdo?|¿Quién tenía razón?}",
    "{La respuesta rápida es|El instinto dice|Tu primera idea fue} <trap>, pero {es|la correcta es} <ans>. {¿Cuál elegiste?|¿Caíste?|¿Y tú?}",
    "<trap> {es la respuesta común|es lo que muchos dicen}, pero {es|resulta ser} <ans>. {¿Tú qué opinas?|¿Quién tenía razón?|¿Cuál dijiste?}",
)
DEBATE_TRAP_SCREEN = ("{MUCHOS DICEN|LA MAYORÍA RESPONDE|EL INSTINTO DICE|CASI TODOS DICEN} <trap>",)
# Sin trampa conocida: se pide la respuesta del espectador, sin inventar porcentajes.
DEBATE_PLAIN = ("<ans> {¿Lo acertaste?|¿Y tú qué dijiste?|¿Coincide con tu respuesta?|¿Quién lo sacó?}",
                "<ans> {¿Era la tuya?|¿Lo viste venir?|¿Te engañó?|¿Qué respondiste?}",
                "{La respuesta es|Respuesta:|Solución:} <ans_l>. {¿Lo sacaste a la primera?|¿Quién tenía razón?|¿Alguien más lo resolvió?}",
                "<ans> {Si dudaste, no eres el único.|Dime si lo adivinaste.|Cuéntame cómo lo pensaste.} {¿Tú qué opinas?|¿Y tú?}")
DEBATE_PLAIN_SCREEN = ("{¿Y TÚ QUÉ DIJISTE?|¿LO ACERTASTE?|COMÉNTALO ABAJO|¿COINCIDE CON TU RESPUESTA?|¿CUÁL ELEGISTE?}",)
# Linea corta antes de la solucion (<= 4 palabras: cabe en 2 s)
DEBATE_PRE = ("{Piénsalo bien|Escribe tu respuesta|Respóndelo en comentarios|No mires la solución}.",
              "{¿Seguro que es fácil?|¿Ya lo sabes?|¿Tienes tu respuesta?}")

# ============================================================================ 4. FRAGMENTOS DE LA PUBLICACION
TITLE_OPEN = ("El 99% falla", "Casi nadie acierta", "Solo 1 de cada 10 lo logra", "Pocos lo consiguen",
              "Esto engaña a casi todos", "No lo resolverás a la primera", "Cuidado con la trampa", "Mucha gente se equivoca",
              "Nivel difícil", "Reto del día", "Solo para valientes", "Prueba de fuego")
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
    "{Pocos|Muy pocos|Casi nadie} {consiguen|logran} <act> en estos <n> <plural>. <emo>",
    "{Mira con calma|Mira bien|Atento}: <n> <plural> y {una trampa en cada uno|más dificultad en cada uno|la respuesta al final}. <emo>",
)
EMOJIS = ("🧠", "👀", "⚡", "🔥", "🎯", "⏱️", "🤔")
COMMENT_ASK = (
    "👇 {Comenta|Escribe|Cuéntame} {cuántos acertaste|tu puntaje|tu nota|en qué reto fallaste} (0 a <n>).",
    "👇 ¿{Cuántos|Cuántos de los <n> retos} {lograste|acertaste}? {Respóndeme|Escríbelo|Dímelo} en los comentarios.",
    "👇 {Dime|Cuéntame} tu {puntaje|resultado} de 0 a <n> y {cuál fue el más difícil|cuál te engañó más|cuál te gustó más}.",
    "👇 {¿Qué reto te costó más?|¿Cuál fue tu reto favorito?|¿En cuál dudaste?} {Cuéntamelo|Escríbelo|Comenta} abajo.",
)
COMMENT_ASK_LOOP = (
    "👇 ¿Cuántas veces {lo repetiste|lo viste}? {Escribe el número|Dímelo|Sé honesto}.",
    "👇 {Cuéntame|Dime} en qué segundo {creíste ver el principio|notaste el empalme}.",
)
SHARE_LINES = (
    "📤 {Mándaselo a quien crea que no lo acierta.|Reta a un amigo: envíale este video.|Compártelo con alguien a quien le encanten los retos.|¿Conoces a alguien que lo resolvería? Envíaselo.|Guárdalo y reta a alguien de tu familia.|Mándaselo a tu amigo más listo y mira si lo logra.|Envíaselo a ese amigo que presume de buena vista.}",
)
FOLLOW_LINES = (
    "➕ {Sígueme: un reto nuevo cada día.|Si te gustó, sígueme: hay más retos todos los días.|Sígueme para el reto de mañana.|Nuevo reto cada día: sígueme para no perdértelo.|Sígueme y entrena tu mente cada día.|Sígueme: mañana viene otro nivel.}",
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


def make_share(rng: random.Random) -> str:
    return pick(rng, SHARE_LINES)


def make_follow(rng: random.Random) -> str:
    return pick(rng, FOLLOW_LINES)


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
    "{¿Cuántos de los <n> retos acertaste?|¿Cuántos de los <n> lograste?|¿Cuál fue tu puntaje, de 0 a <n>?} Responde solo con un número 👇",
    "{Dime|Cuéntame} tu nota de 0 a <n>: {solo el número|con un número} 👇",
    "¿{Llegaste|Llegaste a acertar} los <n>? {Responde con un número|Escribe tu nota|Dime tu puntaje} 👇",
)
PINNED_LOOP = (
    "¿Cuántas veces lo repetiste? Responde solo con un número 👇",
    "{Sé honesto|Dime la verdad}: ¿cuántas veces lo viste seguidas? {Escribe el número|Solo un número} 👇",
)


def make_pinned(rng: random.Random, n: int, loop: bool = False) -> str:
    """Comentario fijado sugerido (una cifra: es lo que mas se responde)."""
    return pick(rng, PINNED_LOOP if loop else PINNED, n=n)
