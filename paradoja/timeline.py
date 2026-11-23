"""Linea de tiempo: uniforms del shader por instante + eventos de sonido."""
from bisect import bisect_right

from .config import VideoSpec
from .scene import LOOP_SCENE_ID, TYPES, Scene, swarm_clock


def _ss(a: float, b: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _flick(act, rt: float) -> int:
    """0 = imagen A, 1 = imagen B (con el cambio), 2 = pantalla vacia."""
    if rt >= act.search:
        return 1
    if act.type == "memory":                      # memoriza 3 s, 1.4 s en blanco, luego la imagen cambiada
        return 0 if rt < 3.0 else 2 if rt < 4.4 else 1
    if rt < 0.8:
        return 0
    ph = (rt - 0.8) % 1.7                         # flicker: A - blanco - B - blanco
    return 0 if ph < 0.6 else 2 if ph < 0.85 else 1 if ph < 1.45 else 2


MAGIC_DOT = 8.0   # px por punto del autoestereograma (mas grande = mas robusto a la compresion)


class Timeline:
    def __init__(self, spec: VideoSpec, scene: Scene):
        self.spec, self.scene = spec, scene
        self.is_loop = scene.mode == "loop"
        self.acts = scene.acts
        self._starts = [a.start for a in self.acts]
        self.outro_start = self.acts[-1].end if self.acts else 0.0

    def act_index(self, t: float) -> int:
        return min(len(self.acts) - 1, max(0, bisect_right(self._starts, t) - 1))

    def uniforms(self, t: float) -> dict:
        if self.is_loop:
            return {"u_time": t, "u_mix": 1.0, "u_pop": 1.0, "u_scene": LOOP_SCENE_ID}

        idx = self.act_index(t)
        act = self.acts[idx]
        ty = TYPES[act.type]
        S, L = act.search, act.length
        rt = t - act.start
        sc = self.scene

        actph = min(max(rt, 0.0), S)                  # reloj de movimiento: se congela al revelar
        tau, hl = 0.0, 0.0
        if act.type == "count":                       # las figuras se detienen 2 s antes de revelar para poder contarlas
            actph = min(max(rt, 0.0), S - 2.0)
        if act.type == "swarm":
            actph = swarm_clock(rt, S, act.q[0])
            hl = 1.0 - _ss(2.0, 2.6, rt)              # el rojo se desvanece a los 2 s
        elif act.type == "sync":                      # tau = 0 justo en el frame del encaje
            tau = (t - act.hit) if rt <= S else (rt - S - 1.2) * 0.015   # al revelar: repeticion lenta

        cols, rows, cell, hexa = act.grid
        u = {
            "_act": idx, "_type": act.type,
            "u_scene": ty.scene_id,
            "u_grid": (float(cols), float(rows)), "u_cell": float(cell), "u_hex": int(hexa),
            "u_sym": act.sym, "u_actshape": act.shape,
            "u_tau": tau, "u_hl": hl,
            "u_time": t,
            "u_mix": 1.0 - _ss(self.outro_start - 0.05, self.outro_start + 0.45, t),
            # el primer acto entra ya formado: el primer fotograma (miniatura) debe mostrar el reto, no un fondo vacio
            "u_pop": (1.0 if idx == 0 else _ss(0.0, 0.45, rt)) * (1.0 - _ss(L - 0.4, L, rt)),
            "u_reveal": _ss(S, S + 0.35, rt),
            "u_revt": max(0.0, rt - S),
            "u_progress": 1.0 - min(1.0, max(0.0, (rt - 0.45) / (S - 0.45))),
            "u_actph": actph,
            "u_kind": act.kind,
            "u_delta": act.delta,
            "u_target": (float(act.target[0]), float(act.target[1])),
            "u_hue": act.hue,
            "u_actp": act.p,
            "u_flick": _flick(act, rt) if act.type in ("flicker", "memory") else 0,
        }
        if act.type == "magiceye":
            period = max(12, round((170 + 60 * act.q[0]) / MAGIC_DOT)) * MAGIC_DOT   # px (multiplo del punto)
            u["u_me"] = (period, period * (0.10 + 0.05 * act.q[1]))
            u["u_dot"] = MAGIC_DOT
        if act.type == "count":
            u["u_cnt"] = act.q
        if act.type in ("cups", "simon", "stroop", "math", "sequence", "riddle"):
            u["u_q"] = act.q
        if act.arrays:
            u["u_n"] = act.n
            u.update(act.arrays)
        return u

    def sfx(self) -> list:
        """[(tiempo, tipo)] con tipo en whoosh|tick|ding|chime."""
        if self.is_loop:  # un campanazo suave al inicio de cada vuelta
            P = self.scene.loop_period
            return [(P * k, "chime") for k in range(1, self.scene.loop_k)]
        ev = [(0.0, "whoosh")] if self.scene.lead > 0 else []      # entrada del gancho
        for a in self.acts:
            ev.append((a.start, "whoosh"))
            if TYPES[a.type].countdown:
                ev += [(a.start + a.search - k, "tick") for k in (3, 2, 1)]
            if a.type == "simon":                     # un tic por cada destello (ayuda a memorizar el orden)
                ev += [(a.start + a.q[1] + k * a.q[0], "tick") for k in range(a.n)]
            ev.append((a.start + a.search, "ding"))
        ev.append((self.outro_start, "chime"))
        return ev
