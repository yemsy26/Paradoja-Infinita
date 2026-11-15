"""Renderizado en GPU (OpenGL headless via moderngl) -> bytes RGB24 por frame."""
import time
from pathlib import Path

import moderngl
import numpy as np

from .config import VideoSpec
from .scene import Scene, shader_static
from .timeline import Timeline

_VERT = """
#version 330
in vec2 in_pos;
void main() { gl_Position = vec4(in_pos, 0.0, 1.0); }
"""


class GpuRenderer:
    def __init__(self, spec: VideoSpec, scene: Scene):
        self.spec = spec
        self.ctx = moderngl.create_standalone_context(require=330)
        self.gpu_name = self.ctx.info["GL_RENDERER"]

        src = (Path(__file__).parent / "shaders" / "scene.frag").read_text(encoding="utf-8")
        self.prog = self.ctx.program(vertex_shader=_VERT, fragment_shader=src)
        quad = self.ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4").tobytes())
        self.vao = self.ctx.vertex_array(self.prog, [(quad, "2f", "in_pos")])
        self.fbo = self.ctx.simple_framebuffer((spec.width, spec.height), components=4)
        self.fbo.use()
        self._uniforms = {n: self.prog[n] for n in self.prog if isinstance(self.prog[n], moderngl.Uniform)}
        self.mode = scene.mode
        self._cur_act = None
        self._textures = []
        self._set({"u_res": (float(spec.width), float(spec.height)), "u_pass": 0, **shader_static(scene)})

    def _set(self, values: dict):
        for name, val in values.items():
            u = self._uniforms.get(name)  # None si el compilador elimino el uniform
            if u is None:
                continue
            if isinstance(val, (bytes, bytearray)):   # arrays de uniforms (enjambre)
                u.write(val)
            else:
                u.value = val

    def _build_stereo(self, ufs: dict):
        """Ojo magico: pasada de profundidad -> CPU integra la fase por fila -> texturas u_phi / u_dep."""
        W, H = self.spec.width, self.spec.height
        self._set(ufs)
        self._set({"u_pass": 1})
        self.vao.render(moderngl.TRIANGLE_STRIP)
        raw = np.frombuffer(self.fbo.read(components=3, alignment=1), np.uint8).reshape(H, W, 3)[:, :, 0].copy()
        period, shift = ufs["u_me"]
        dep = raw.astype("f4") / 255.0
        phi = np.cumsum(1.0 / (period - shift * dep), axis=1, dtype=np.float32)   # fase en periodos
        for t in self._textures:
            t.release()
        t_phi = self.ctx.texture((W, H), 1, phi.tobytes(), dtype="f4")
        t_dep = self.ctx.texture((W, H), 1, dep.tobytes(), dtype="f4")
        for loc, t in enumerate((t_phi, t_dep)):
            t.filter = (moderngl.NEAREST, moderngl.NEAREST)
            t.use(location=loc)
        self._textures = [t_phi, t_dep]
        self._set({"u_pass": 0, "u_phi": 0, "u_dep": 1})

    def frames(self, timeline: Timeline):
        """Generador de frames RGB24 (bytes) a spec.fps."""
        spec = self.spec
        t0 = time.perf_counter()
        for i in range(spec.frames):
            ufs = timeline.uniforms(i / spec.fps)
            act = ufs.pop("_act", None)
            if self.mode == "magiceye" and act != self._cur_act:   # nueva prueba: recalcular estereograma
                self._cur_act = act
                self._build_stereo(ufs)
            self._set(ufs)
            self.vao.render(moderngl.TRIANGLE_STRIP)
            yield self.fbo.read(components=3, alignment=1)
            if (i + 1) % 600 == 0:
                fps = (i + 1) / (time.perf_counter() - t0)
                print(f"  frame {i + 1}/{spec.frames}  ({fps:.0f} fps de render)", flush=True)
