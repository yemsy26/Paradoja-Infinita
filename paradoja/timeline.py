"""Linea de tiempo: uniforms del shader por instante + eventos de sonido."""
from .config import REVEAL_LEN, VideoSpec
from .scene import Scene, swarm_clock


def _ss(a: float, b: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


class Timeline:
    def __init__(self, spec: VideoSpec, scene: Scene):
        self.spec, self.scene = spec, scene
        self.is_loop = scene.mode == "loop"
        n = len(scene.acts)
        if self.is_loop:
            self.hook_len = self.outro_start = 0.0
            self.act_len = self.search_len = 0.0
        else:
            self.hook_len = scene.hook_len
            self.act_len = (spec.duration - scene.hook_len - scene.outro_len) / n
            self.search_len = self.act_len - REVEAL_LEN
            self.outro_start = scene.hook_len + n * self.act_len

    def act_start(self, i: int) -> float:
        return self.hook_len + i * self.act_len

    def uniforms(self, t: float) -> dict:
        if self.is_loop:
            return {"u_time": t, "u_mix": 1.0, "u_pop": 1.0}

        sc, L, S = self.scene, self.act_len, self.search_len
        idx = min(len(sc.acts) - 1, max(0, int((t - self.hook_len) // L)))
        act = sc.acts[idx]
        rt = t - self.act_start(idx)
        mix = min(_ss(self.hook_len - 0.45, self.hook_len + 0.05, t),
                  1.0 - _ss(self.outro_start - 0.05, self.outro_start + 0.45, t))
        mode = sc.mode
        actph = min(max(rt, 0.0), S)                  # reloj de movimiento: se congela al revelar
        tau, hl = 0.0, 0.0
        if mode == "swarm":
            actph = swarm_clock(rt, S, act.q[0])
            hl = 1.0 - _ss(2.0, 2.6, rt)              # el rojo se desvanece a los 2 s
        elif mode == "sync":                          # tau = 0 justo en el frame del encaje
            tau = (t - act.hit) if rt <= S else (rt - S - 1.2) * 0.015   # al revelar: repeticion en camara lenta
        u = {
            "_act": idx,
            "u_sym": act.sym,
            "u_actshape": act.shape,
            "u_tau": tau,
            "u_hl": hl,
            "u_time": t,
            "u_mix": mix,
            "u_pop": _ss(0.0, 0.45, rt) * (1.0 - _ss(L - 0.4, L, rt)),
            "u_reveal": _ss(S, S + 0.35, rt),
            "u_revt": max(0.0, rt - S),
            "u_progress": 1.0 - min(1.0, max(0.0, (rt - 0.45) / (S - 0.45))),
            "u_actph": actph,
            "u_kind": act.kind,
            "u_delta": act.delta,
            "u_target": (float(act.target[0]), float(act.target[1])),
            "u_hue": act.hue,
            "u_actp": act.p,
        }
        if mode == "magiceye":
            period = (int(32 + act.q[0] * 12)) * 5.0   # px; puntos de 5 px (ver shader)
            u["u_me"] = (period, period * (0.10 + 0.05 * act.q[1]))
        if act.arrays:
            u["u_n"] = act.n
            u.update(act.arrays)
        return u

    def sfx(self) -> list:
        """[(tiempo, tipo)] con tipo en whoosh|tick|ding|chime."""
        if self.is_loop:  # un campanazo suave al inicio de cada vuelta
            P = self.scene.loop_period
            return [(P * k, "chime") for k in range(1, self.scene.loop_k)]
        ev = [(0.0, "whoosh")]
        for i in range(len(self.scene.acts)):
            s = self.act_start(i)
            ev.append((s, "whoosh"))
            if self.scene.mode != "swarm":
                ev += [(s + self.search_len - k, "tick") for k in (3, 2, 1)]
            ev.append((s + self.search_len, "ding"))
        ev.append((self.outro_start, "chime"))
        return ev
