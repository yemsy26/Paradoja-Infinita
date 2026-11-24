"""Politica de texto: nada de lo que se publica menciona la IA ni usa cebos de interaccion que Meta penaliza.

Se generan cientos de videos e imagenes (sin renderizar) y se pasa por `copy_guard` todo lo que acaba en Facebook: la voz, las
fichas en pantalla, el titulo, la descripcion, los hashtags, el `_publicar.txt` y el texto alternativo.
"""
import inspect
import random
import re

import pytest

from paradoja import catalog, copy_es, texts_es
from paradoja.config import VideoSpec
from paradoja.copy_guard import BAIT_PATTERNS, find_issues, first_issue
from paradoja.feed import canvas, copy_feed, render
from paradoja.feed import history as feed_history
from paradoja.feed import puzzles as P
from paradoja.feed.studio import choose_mode
from paradoja.metadata import build_post, write_metadata
from paradoja.scene import MODES, build_scene
from paradoja.script_es import build_script
from paradoja.spin import expand_all
from paradoja.subtitles import build_ass
from paradoja.timeline import Timeline

SPEC = VideoSpec()
SEEDS = range(1, 26)
USER_EXAMPLES_OF_BAIT = (
    "Solo el 1% de las personas lo resuelve", "El 99% falla este reto", "La mayoría se equivoca", "Casi nadie acierta",
    "Comenta SÍ si lo lograste", "Comenta tu respuesta abajo", "Etiqueta a un amigo que lo necesite", "Etiqueta a 3 amigos",
    "Compártelo con alguien", "Mándaselo a tu amigo más listo", "Guarda este video", "Dale like si lo sacaste",
    "Solo los más listos lo logran", "Muchos dicen 24, pero es 18", "Solo si tienes un IQ alto", "Eres de los pocos",
    "Reta a un amigo", "Dime tu nota en los comentarios", "👇 Escribe tu respuesta", "Únete al 1% que gana",
)
AI_MENTIONS = ("Generado por IA", "hecho con inteligencia artificial", "Voz sintética", "narración neuronal", "#IA", "con AI",
               "creado con ChatGPT", "contenido artificial", "imágenes con Midjourney", "un robot lo narra")
CLEAN_TEXTS = ("Si me compartes, ya no me tienes. ¿Qué soy?", "Sigue el punto rojo", "Tiene raíces que nadie ve",
               "Chiquito como un ratón y guarda la casa como un león", "¿Cuántos cubos hay en total?", "Pon a prueba tu cerebro",
               "¿Cuántas veces se escribe la cifra 9 del 1 al 100?", "Mira con calma: la solución llega al final",
               "5 máquinas hacen 5 piezas en 5 minutos", "¿Qué número sigue? 2, 4, 8, 16")


def _scene(mode, seed):
    sc = build_scene(seed, mode, SPEC)
    return sc, Timeline(SPEC, sc)


# --------------------------------------------------------------------------- el filtro
@pytest.mark.parametrize("text", USER_EXAMPLES_OF_BAIT)
def test_the_filter_catches_every_bait_pattern(text):
    assert find_issues(text), text


@pytest.mark.parametrize("text", AI_MENTIONS)
def test_the_filter_catches_every_mention_of_ai(text):
    assert any(name in ("IA", "inteligencia artificial", "voz sintética", "modelo", "generado") for name, _ in find_issues(text)), text


@pytest.mark.parametrize("text", CLEAN_TEXTS)
def test_the_filter_lets_natural_text_and_riddles_through(text):
    assert find_issues(text) == [], (text, find_issues(text))


def test_a_plain_follow_invitation_is_only_allowed_where_asked():
    assert find_issues("Sígueme para el reto de mañana.") and not find_issues("Sígueme para el reto de mañana.", allow_follow=True)
    assert first_issue(["limpio", "Comenta tu nota"]) and first_issue(["limpio", "otro limpio"]) is None
    assert set(BAIT_PATTERNS) >= {"estadística inventada", "afirmación sobre la mayoría", "pide comentar", "pide compartir o enviar",
                                  "pide etiquetar o mencionar"}


# --------------------------------------------------------------------------- videos
def test_every_hook_cta_and_debate_template_is_clean():
    pools = [copy_es.HOOKS_GENERIC, *copy_es.HOOKS_BY_CATEGORY.values(), copy_es.HOOKS_LOOP, copy_es.DEBATE_TRAP,
             copy_es.DEBATE_TRAP_SCREEN, copy_es.DEBATE_PLAIN, copy_es.DEBATE_PLAIN_SCREEN, copy_es.DEBATE_PRE,
             copy_es.TITLE_OPEN, copy_es.TITLE_CLOSE, copy_es.DESC_OPEN, copy_es.COMMENT_ASK, copy_es.COMMENT_ASK_LOOP,
             copy_es.CLOSERS, copy_es.SEO_TAIL, copy_es.PINNED, copy_es.PINNED_LOOP, texts_es.HOOK_SHORT, texts_es.OUTRO,
             texts_es.LOOP_OUTRO]
    for pool in pools:
        for tpl in pool:
            for text in expand_all(tpl):
                assert not find_issues(text), (text, find_issues(text))
    for pool in (copy_es.CTAS, copy_es.CTAS_LOOP):                        # el cierre solo invita a seguir la pagina
        for tpl in pool:
            for text in expand_all(tpl):
                assert not find_issues(text, allow_follow=True), (text, find_issues(text, allow_follow=True))
    for cat_texts in texts_es.HOOK_TEXT.values():
        assert all(not find_issues(t) for t in cat_texts)
    assert not hasattr(copy_es, "SHARE_LINES") and not hasattr(copy_es, "FOLLOW_LINES")      # sin lineas de compartir ni seguir


@pytest.mark.parametrize("mode", MODES)
def test_every_video_is_clean_in_voice_screen_and_post(mode, tmp_path):
    for seed in SEEDS:
        sc, tl = _scene(mode, seed)
        for seg in build_script(sc, tl):                                              # lo que dice la voz
            assert not find_issues(seg.text, allow_follow=True), (mode, seed, seg.text, find_issues(seg.text, allow_follow=True))
        ass = build_ass(tmp_path / "s.ass", [], tl, SPEC).read_text("utf-8")            # lo que se quema en pantalla
        assert not find_issues(ass, allow_follow=True), (mode, seed, find_issues(ass, allow_follow=True))
        post = build_post(sc, tl)                                                     # lo que se publica
        for part in ("title", "desc", "footer", "paste", "pinned"):
            assert not find_issues(post[part]), (mode, seed, part, post[part], find_issues(post[part]))
        assert not re.search(r"[👇📤➕]", post["paste"])


@pytest.mark.parametrize("mode", ["anomaly", "riddle", "math", "mix", "loop"])
def test_the_files_written_for_a_video_never_mention_ai(mode, tmp_path):
    sc, tl = _scene(mode, 77)
    path, _title, _h = write_metadata(tmp_path / "v.txt", sc, tl, "v.mp4")
    paste = (tmp_path / "v_publicar.txt").read_text("utf-8-sig")
    assert not find_issues(paste), find_issues(paste)
    text = path.read_text("utf-8-sig")
    ai = [i for i in find_issues(text) if i[0] in ("IA", "inteligencia artificial", "voz sintética", "modelo", "generado")]
    assert not ai, ai
    assert "Etiqueta de IA" not in text and "ANTES DE PUBLICAR" not in text


def test_the_post_pool_is_still_varied_after_removing_the_bait():
    pastes = {build_post(*_scene("sync", s))["paste"] for s in range(1, 41)}
    assert len(pastes) >= 35
    hooks = {build_scene(s, "mix", SPEC).hook for s in range(1, 200)}
    assert len(hooks) >= 120


# --------------------------------------------------------------------------- imagenes
@pytest.mark.parametrize("kind", P.MODES)
def test_every_image_post_and_alt_text_is_clean(kind):
    for seed in range(1, 81):
        puz = P.generate(kind, seed)
        post = copy_feed.build_post(puz, seed)
        for text in (post["paste"], post["hook"], post["ask"], puz.alt):
            assert not find_issues(text), (kind, seed, text, find_issues(text))
        assert not re.search(r"[👇📤➕]", post["paste"])


def test_the_text_drawn_on_the_images_is_clean():
    strings = [*render.CUBE_SUBS, *render.OPTION_HEADS]
    defaults = inspect.signature(canvas.Canvas.frame).parameters
    strings += [defaults["cta"].default, defaults["sub"].default]
    assert all(not find_issues(s) for s in strings), [(s, find_issues(s)) for s in strings if find_issues(s)]
    assert "COMENTA" not in defaults["cta"].default and "SÍGUENOS" not in defaults["sub"].default


# --------------------------------------------------------------------------- anti-repeticion en los generadores
def test_video_generator_avoids_the_requested_formats():
    for _ in range(5):
        seed, mode = catalog.choose("random", [], SPEC, tries=24, avoid=tuple(m for m in MODES if m != "simon"))
        assert mode == "simon"                                                      # solo queda un formato permitido
    seen = {catalog.choose("random", [], SPEC, tries=24, avoid=("mix",))[1] for _ in range(40)}
    assert "mix" not in seen and len(seen) > 5
    assert catalog.choose("random", [], SPEC, tries=24, avoid=tuple(MODES))[1] in MODES    # todo evitado: igual elige uno


def test_image_generator_avoids_the_requested_types(tmp_path):
    rng = random.Random(1)
    assert {feed_history.pick_mode([], rng, avoid=("pemdas", "cubos")) for _ in range(30)} <= {"fracciones", "opciones"}
    assert {choose_mode("aleatorio", tmp_path, rng, avoid=("pemdas", "cubos")) for _ in range(30)} <= {"fracciones", "opciones"}
    assert feed_history.pick_mode([], rng, avoid=tuple(P.MODES)) in P.MODES              # todo evitado: igual elige uno
    assert choose_mode("cubos", tmp_path, rng, avoid=("cubos",)) == "cubos"              # un tipo concreto se respeta siempre
