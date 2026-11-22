#version 330
// Convencion: px.y crece hacia ABAJO de la imagen (la fila 0 de glReadPixels es el borde superior
// del video), asi no hace falta ningun vflip en CPU.
//
// u_scene: 0 anomalia | 1 ilusion | 2 bucle | 3 sincronizacion (pause game) | 4 ishihara
//          5 enjambre | 6 ojo magico (autostereograma) | 7 contraste | 8 conteo | 9 flicker/memoria | 10 fondo de texto
// u_scene y los parametros de rejilla cambian por ACTO (un video mixto combina varios tipos).
// Todo (paleta, forma, layout, movimiento, velocidad, tipo de gancho/ilusion/bucle) llega por uniforms
// decididos por la semilla en scene.py.

uniform vec2  u_res;
uniform float u_time, u_speed, u_mix, u_pop, u_reveal, u_revt, u_progress, u_delta, u_actph;
uniform float u_hue, u_spin, u_loopP, u_cell;
uniform int   u_scene, u_kind, u_shape, u_motion, u_bgstyle, u_hook, u_hooksides, u_loopkind, u_hex;
uniform vec2  u_target, u_actp, u_grid, u_sv;
uniform vec4  u_rnd;
uniform vec3  u_lint, u_bg1, u_bg2, u_tuna, u_tunb, u_accent;
// modos nuevos
uniform int   u_pass, u_sym, u_actshape, u_n;      // u_pass=1: pasada de profundidad (ojo magico)
uniform float u_tau, u_hl, u_flick;                // u_flick: 0 imagen A, 1 imagen B, 2 vacio
uniform vec2  u_cnt;                               // conteo: filtro de figura (-1 = cualquiera), filtro de tono
uniform vec2  u_q;                                 // parametros del reto: vasos, Simon (ver cada escena)
uniform vec2  u_me;                                // ojo magico: periodo (px), desplazamiento maximo (px)
uniform float u_dot;                               // ojo magico: tamaño del punto (px)
uniform vec4  u_pa[40], u_pb[40];                  // enjambre (40 = SWARM_MAX)
uniform sampler2D u_phi, u_dep;                    // ojo magico: fase acumulada y mapa de profundidad
out vec4 fragColor;

const float TAU = 6.2831853;
const float PI  = 3.14159265;
const vec2  ICENTER = vec2(0.0, -0.296);   // centro de las ilusiones (px.y=640), por encima de los subtitulos

// ------------------------------------------------------------------ utilidades
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}
float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}
// Anti-aliasing de sign(s) con derivadas de pantalla.
float edge(float s) {
    float w = fwidth(s) + 1e-4;
    return clamp(0.5 + 0.5 * s / w, 0.0, 1.0);
}
vec2 rot(vec2 p, float a) {
    float c = cos(a), s = sin(a);
    return vec2(c * p.x - s * p.y, s * p.x + c * p.y);
}

// ------------------------------------------------------------------ SDF de figuras
float sdNgon(vec2 p, float r, float n) {
    float an = PI / n;
    float bn = mod(atan(p.x, p.y), 2.0 * an) - an;
    p = length(p) * vec2(cos(bn), abs(sin(bn)));
    p -= r * vec2(cos(an), sin(an));
    p.y += clamp(-p.y, 0.0, r * sin(an));
    return length(p) * sign(p.x);
}
float sdStar(vec2 p, float r, float n, float m) {
    float an = PI / n, en = PI / m;
    vec2 acs = vec2(cos(an), sin(an)), ecs = vec2(cos(en), sin(en));
    float bn = mod(atan(p.x, p.y), 2.0 * an) - an;
    p = length(p) * vec2(cos(bn), abs(sin(bn)));
    p -= r * acs;
    p += ecs * clamp(-dot(p, ecs), 0.0, r * acs.y / ecs.y);
    return length(p) * sign(p.x);
}
// Figura elegida por la semilla; s = factor de escala (1 = tamaño base 0.36 de celda).
float shapeSDi(vec2 p, float s, int idx) {
    p.y = -p.y;                                        // y de la imagen hacia abajo: triangulo y estrella quedan derechos
    if (idx == 0) return length(p) - 0.36 * s;
    if (idx == 1) return sdNgon(p, 0.43 * s, 3.0);
    if (idx == 2) return sdNgon(p, 0.40 * s, 4.0);
    if (idx == 3) return sdNgon(p, 0.40 * s, 6.0);
    if (idx == 4) return sdStar(p, 0.42 * s, 5.0, 2.6);
    if (idx == 5) return sdNgon(p, 0.40 * s, 5.0);
    vec2 d = abs(p) - vec2(0.30 * s);
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - 0.06 * s;
}
float shapeSD(vec2 p, float s) { return shapeSDi(p, s, u_shape); }

// ------------------------------------------------------------------ fondo
vec3 background(vec2 px) {
    vec2 uv = px / u_res;
    float T = u_time * u_speed * 0.12;
    float v;
    if (u_bgstyle == 0) {
        v = sin(uv.x * 3.0 + T + u_rnd.x * 6.0) + sin(uv.y * 4.0 - T * 1.3 + u_rnd.y * 6.0)
          + sin((uv.x + uv.y) * 5.0 + T * 0.7);
        v = v / 3.0 * 0.5 + 0.5;
    } else if (u_bgstyle == 1) {
        float r = length((uv - 0.5) * vec2(1.0, 1.78));
        v = 0.5 + 0.5 * sin(r * (6.0 + u_rnd.x * 8.0) - T * 8.0);
    } else if (u_bgstyle == 2) {
        v = 0.5 + 0.5 * sin((uv.x + uv.y) * (10.0 + u_rnd.y * 16.0) - T * 10.0);
    } else {
        vec2 q = uv * vec2(12.0, 21.0) + vec2(T * 3.0, -T * 2.0);
        v = 0.5 + 0.5 * sin(q.x) * sin(q.y);
    }
    return mix(u_bg1, u_bg2, v * 0.85);
}

// ------------------------------------------------------------------ GANCHO (3 variantes)
vec3 hookScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / (0.5 * u_res.y);
    float T = u_time * u_speed;
    float r = length(p) + 1e-4;
    float c;
    if (u_hook == 0) {                                         // tunel log-polar
        float a = atan(p.y, p.x), lr = log(r);
        float arms = floor(4.0 + u_rnd.x * 6.0);
        float k  = lr * 2.2 - T * 0.45;
        float tw = a * arms + lr * (2.0 + u_rnd.z * 3.0) - T * (u_rnd.y - 0.5) * 1.6;
        c = abs(edge(sin(k * TAU)) - edge(sin(tw)));
    } else if (u_hook == 1) {                                  // tunel de poligonos
        float n = float(u_hooksides), an = PI / n;
        vec2 q = rot(p, log(r) * (u_rnd.y - 0.5) * 3.0 + T * 0.25 * (u_rnd.z - 0.5));
        float bn = mod(atan(q.x, q.y), 2.0 * an) - an;
        float gauge = length(q) * cos(bn) + 1e-4;
        float k = log(gauge) * 2.4 - T * 0.5;
        c = abs(edge(sin(k * TAU)) - edge(sin(atan(q.x, q.y) * n)));
    } else {                                                   // caleidoscopio
        float n = float(u_hooksides), an = PI / n;
        float a = abs(mod(atan(p.y, p.x), 2.0 * an) - an);
        vec2 q = r * vec2(cos(a), sin(a)) + 0.35 * vec2(sin(T * 0.7), cos(T * 0.5));
        float v = sin(q.x * 9.0 + T) + sin(q.y * 11.0 - T * 1.2) + sin(length(q) * 14.0 - T * 2.0);
        c = edge(sin(v * 2.0));
    }
    vec3 col = mix(u_tunb, u_tuna, c);
    col += u_tuna * exp(-r * 4.5) * 0.55;
    col *= 1.0 - 0.45 * smoothstep(0.7, 1.7, r);
    col *= 0.92 + 0.08 * sin(T * 3.0);
    return col;
}

// ------------------------------------------------------------------ barra de tiempo
vec3 timerBar(vec3 col, vec2 px) {
    vec2 bc = vec2(0.5 * u_res.x, 280.0);
    vec2 dq = abs(px - bc) - vec2(450.0, 10.0) + 10.0;
    float sd = length(max(dq, 0.0)) + min(max(dq.x, dq.y), 0.0) - 10.0;
    float track = 1.0 - smoothstep(-1.0, 1.0, sd);
    float fx = (px.x - (bc.x - 450.0)) / 900.0;
    col = mix(col, vec3(0.0), track * 0.45 * u_pop);
    return mix(col, mix(vec3(1.0, 0.25, 0.15), u_accent, u_progress), track * step(fx, u_progress) * u_pop);
}

// ------------------------------------------------------------------ MODO 1: anomalia
vec2 motionOf(vec2 id) {
    float ph = hash21(id + u_rnd.w * 31.7) * TAU;
    float T = u_time * u_speed;
    float amp = (u_shape == 0) ? 0.055 : 0.045;
    if (u_motion == 0) return amp * vec2(sin(T * 1.2 + ph), cos(T * 0.9 + ph * 1.7));
    if (u_motion == 1) return amp * vec2(cos(T * 1.6 + ph), sin(T * 1.6 + ph));
    if (u_motion == 2) return amp * vec2(sin(T * 1.3 + id.x * 0.9 + id.y * 0.5), 0.0);
    return amp * vec2(0.0, sin(T * 1.5 + id.x * 0.8 - id.y * 0.6));
}

vec3 drawCell(vec3 col, vec2 id, vec2 f) {
    float h = hash21(id + u_rnd.w * 31.7);
    float ph = h * TAU;
    bool odd = all(equal(id, u_target));
    float T = u_time * u_speed;

    float hue = u_hue + (h - 0.5) * 0.010;
    float val = u_sv.y + (hash21(id + 9.1) - 0.5) * 0.05;
    float sc = (1.0 + 0.02 * sin(T * 1.7 + ph)) * u_pop;
    float ang = u_spin * T;
    vec2 dotOff = vec2(0.0);
    if (u_scene == 9) {                                // flicker/memoria: el cambio solo existe en la imagen B
        if (odd && u_flick > 0.5 && u_flick < 1.5) {
            if (u_kind == 0)      hue += 0.28 * u_delta;
            else if (u_kind == 1) sc *= 1.0 - 0.5 * u_delta;
            else if (u_kind == 2) val += 0.35 * u_delta;
            else if (u_kind == 3) dotOff = 0.30 * u_delta * vec2(cos(u_rnd.z * TAU), sin(u_rnd.z * TAU));
            else if (u_kind == 4) ang += 0.8 * u_delta;
            else                  sc = 0.0;            // la figura desaparece
        }
    } else if (odd) {
        if (u_kind == 0)      hue += 0.09 * u_delta;
        else if (u_kind == 1) sc *= 1.0 - 0.22 * u_delta;
        else if (u_kind == 2) val += 0.26 * u_delta;
        else if (u_kind == 3) dotOff = 0.20 * u_delta * vec2(cos(u_rnd.z * TAU), sin(u_rnd.z * TAU));
        else                  ang += 0.9 * u_delta;
    }

    vec2 q = rot(f - motionOf(id), ang);
    float d = shapeSD(q, sc);
    float aa = 1.5 / u_cell;
    float m = 1.0 - smoothstep(-aa, aa, d);

    vec3 c = hsv2rgb(vec3(hue, u_sv.x, val));
    float t = clamp(length(q) / (0.40 * max(sc, 1e-3)), 0.0, 1.0);
    c *= 0.78 + 0.32 * (1.0 - t * t);
    c += 0.12 * exp(-length(q - 0.36 * sc * vec2(-0.35, -0.4)) * 14.0);
    float dd = length(q - dotOff) - 0.10 * u_pop;
    c = mix(c, vec3(1.0), (1.0 - smoothstep(-aa, aa, dd)) * 0.9);

    float dim = odd ? 1.0 : mix(1.0, 0.35, u_reveal);
    vec3 glow = hsv2rgb(vec3(hue, 0.6 * u_sv.x + 0.0, 1.0)) * 0.18 * exp(-max(d, 0.0) * 16.0) * u_pop * dim;
    return mix(col + glow, c * dim, m);
}

vec3 anomalyScene(vec2 px) {
    vec3 col = background(px);
    float cell = u_cell;
    float wTot = (u_grid.x + 0.5 * float(u_hex)) * cell;
    vec2 origin = vec2(0.5 * (u_res.x - wTot), 0.5 * (u_res.y - u_grid.y * cell));
    vec2 g = (px - origin) / cell;
    float row = floor(g.y);
    float sh = (u_hex == 1 && mod(row, 2.0) > 0.5) ? 0.5 : 0.0;
    vec2 id = vec2(floor(g.x - sh), row);

    bool hidden = (u_scene == 9 && u_flick > 1.5);
    if (!hidden && id.x >= 0.0 && id.x < u_grid.x && id.y >= 0.0 && id.y < u_grid.y)
        col = drawCell(col, id, vec2(fract(g.x - sh), fract(g.y)) - 0.5);

    // anillo + ondas sobre el objetivo al revelar
    float tsh = (u_hex == 1 && mod(u_target.y, 2.0) > 0.5) ? 0.5 : 0.0;
    vec2 tc = origin + (vec2(u_target.x + 0.5 + tsh, u_target.y + 0.5) + motionOf(u_target)) * cell;
    float dist = length(px - tc) / cell;
    float ring = exp(-pow((dist - (0.46 + 0.03 * sin(u_time * 9.0))) / 0.018, 2.0));
    float ripple = 0.0;
    for (int i = 0; i < 3; i++) {
        float ph = fract(u_revt * 0.7 + float(i) / 3.0);
        ripple += exp(-pow((dist - (0.4 + ph * 1.6)) / 0.03, 2.0)) * (1.0 - ph);
    }
    col += (u_accent * ring + u_accent * ripple * 0.5) * u_reveal;
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 2: ilusiones opticas
// Todas reciben p (px normalizado por el ancho, origen en el centro) y devuelven el color.
// u_actph = reloj de movimiento (se congela al revelar), u_reveal = "desenmascarar" la ilusion.

vec3 illOuchi(vec2 p) {
    float R = 0.26;
    float sh = 0.045 * sin(u_actph * (1.4 + u_actp.x)) * (1.0 - u_reveal);
    vec2 q = p + vec2(sh, sh * 0.6);
    float s = 0.8 + 0.6 * u_actp.y;
    float wl = 0.10 * s, ws = 0.026 * s;
    float outer = abs(edge(sin(q.x / wl * PI)) - edge(sin(q.y / ws * PI)));
    float inner = abs(edge(sin(q.x / ws * PI)) - edge(sin(q.y / wl * PI)));
    float disc = 1.0 - smoothstep(R - 0.004, R + 0.004, length(p - ICENTER));
    vec3 col = mix(u_tunb, u_tuna, mix(outer, inner, disc));
    float ring = exp(-pow((length(p - ICENTER) - R) / 0.006, 2.0));
    return mix(col, u_accent, ring * u_reveal);
}

vec3 illCafe(vec2 p) {
    float h = 0.09 * (0.85 + 0.4 * u_actp.x);
    float row = floor(p.y / h);
    float odd = mod(row, 2.0);
    float shiftf = 0.5 * (0.9 + 0.2 * u_actp.y);
    float x = p.x + odd * h * shiftf + (odd * 2.0 - 1.0) * 0.03 * u_actph;
    float ck = edge(sin(x / h * PI));
    vec3 col = mix(u_tunb, u_tuna, ck);
    float fy = fract(p.y / h);
    float m = min(fy, 1.0 - fy) * h;
    float wl = 0.0028 * (1.0 + 2.0 * u_reveal);     // mortero fino: asi funciona la ilusion
    float line = 1.0 - smoothstep(wl - 0.0006, wl + 0.0006, m);
    return mix(col, mix(mix(u_tunb, u_tuna, 0.5), u_accent, u_reveal), line);
}

vec3 illEbbinghaus(vec2 p, vec3 bg) {
    float flip = u_actp.x > 0.5 ? 1.0 : -1.0;
    vec3 col = bg;
    vec3 surround = mix(u_tuna, u_tunb, 0.55);
    float ph = u_actph * 0.4;
    for (int s = 0; s < 2; s++) {
        float side = (s == 0) ? -1.0 : 1.0;
        vec2 c = vec2(0.255 * side, ICENTER.y);
        bool big = (side * flip) < 0.0;
        float n = big ? 6.0 : 9.0;
        float dist = big ? 0.17 : 0.105;
        float rad = big ? 0.072 : 0.024;
        vec2 v = p - c;
        float an = TAU / n;
        float aa = mod(atan(v.y, v.x) - ph * side + an * 0.5, an) - an * 0.5;
        vec2 q = length(v) * vec2(cos(aa), sin(aa)) - vec2(dist, 0.0);
        float d = shapeSD(q, rad / 0.36);
        col = mix(col, surround, 1.0 - smoothstep(-0.0015, 0.0015, d));
        float dc = length(v) - 0.05;
        col = mix(col, u_accent, 1.0 - smoothstep(-0.0015, 0.0015, dc));
        float ring = exp(-pow((length(v) - 0.064) / 0.003, 2.0));
        col = mix(col, vec3(1.0), ring * u_reveal);
    }
    return col;
}

vec3 illScintillating(vec2 p) {
    float s = 0.15 * (0.8 + 0.5 * u_actp.x);
    vec2 q = rot(p, u_actph * 0.06 * (u_actp.y > 0.5 ? 1.0 : -1.0));
    vec2 f = abs(fract(q / s + 0.5) - 0.5) * s;       // distancia a la linea mas cercana en cada eje
    vec3 base = u_tunb * 0.5;
    float line = 1.0 - smoothstep(0.011, 0.013, min(f.x, f.y));
    float spot = 1.0 - smoothstep(0.022 * (1.0 + 0.4 * u_reveal), 0.025 * (1.0 + 0.4 * u_reveal), length(f));
    vec3 col = mix(base, mix(base, u_tuna, 0.35 * (1.0 - 0.6 * u_reveal)), line);
    return mix(col, mix(u_tuna, u_accent, u_reveal), spot);
}

vec3 illSpiral(vec2 p) {
    vec2 v = p - ICENTER;
    float r = length(v) + 1e-4;
    float arms = floor(2.0 + u_actp.x * 4.0);
    float dir = u_actp.y > 0.5 ? 1.0 : -1.0;
    float ph = atan(v.y, v.x) * arms + log(r) * (3.0 + u_actp.y * 3.0) * dir - u_actph * 2.6;
    vec3 col = mix(u_tunb, u_tuna, edge(sin(ph)));
    return mix(col, u_accent, 1.0 - smoothstep(0.010, 0.013, r));   // punto de fijacion
}

vec3 illMoire(vec2 p) {
    float f = 150.0 + u_actp.x * 120.0;
    float la, lb;
    if (u_actp.y > 0.5) {                                // dos mallas de anillos
        vec2 c2 = ICENTER + 0.06 * vec2(cos(u_actph * 0.7), sin(u_actph * 0.9));
        la = edge(sin(f * length(p - ICENTER)));
        lb = edge(sin(f * length(p - c2)));
    } else {                                             // dos mallas de lineas
        float th = 0.20 * sin(u_actph * 0.5 + u_actp.x * 6.0);
        la = edge(sin(f * dot(p, vec2(cos(0.2), sin(0.2)))));
        lb = edge(sin(f * dot(p, vec2(cos(0.2 + th), sin(0.2 + th)))));
    }
    vec3 col = mix(u_tunb, u_tuna, (1.0 - la) * (1.0 - lb));
    vec3 sep = mix(mix(u_tunb, u_tuna, 1.0 - la), u_accent, 0.6 * lb);
    return mix(col, sep, u_reveal);
}

// --- ilusiones 6-9: rejilla de Hermann, Muller-Lyer, triangulo de Kanizsa, Zollner
float sdSeg(vec2 p, vec2 a, vec2 b);                    // definida mas abajo (digitos de 7 segmentos)

vec3 illHermann(vec2 p) {                               // puntos grises fantasma en los cruces de las lineas claras
    float s = 0.115 + 0.03 * u_actp.x, w = 0.030;
    vec2 g = (p - ICENTER + vec2(0.0, u_actph * 0.012)) / s;
    vec2 f = abs(fract(g + 0.5) - 0.5);                 // distancia (en celdas) a la linea mas cercana
    float wl = w / s;
    float lane = 1.0 - smoothstep(wl - 0.02, wl + 0.02, min(f.x, f.y));
    vec3 col = mix(u_tunb * 0.35, u_tuna, lane);
    float cross = 1.0 - smoothstep(wl * 0.55, wl * 0.75, length(f));      // centro exacto de cada cruce
    col = mix(col, u_accent, cross * u_reveal);         // al revelar, los cruces son tan claros como la linea
    return col;
}

float mlLine(vec2 p, float y, float L, float fin) {     // linea con aletas: fin=+1 flechas hacia fuera, -1 hacia dentro
    float d = sdSeg(p, vec2(-L, y), vec2(L, y));
    float fx = 0.09 * cos(0.55), fy = 0.09 * sin(0.55);
    for (int i = 0; i < 2; i++) {
        float sx = (i == 0) ? -1.0 : 1.0;
        vec2 e = vec2(sx * L, y);
        float dx = (fin > 0.0) ? -sx * fx : sx * fx;
        d = min(d, sdSeg(p, e, e + vec2(dx, fy)));
        d = min(d, sdSeg(p, e, e + vec2(dx, -fy)));
    }
    return d - 0.007;
}
vec3 illMullerLyer(vec2 p) {                            // dos lineas IGUALES: la de aletas hacia dentro parece mas larga
    float L = 0.26;
    float swap = (u_actp.x < 0.5) ? 1.0 : -1.0;
    float y1 = ICENTER.y - 0.13, y2 = ICENTER.y + 0.13;
    float d1 = mlLine(p, y1, L, swap), d2 = mlLine(p, y2, L, -swap);
    vec3 col = u_tunb;
    col = mix(col, u_tuna, 1.0 - smoothstep(-0.001, 0.002, min(d1, d2)));
    float guide = exp(-pow((abs(abs(p.x) - L) - 0.0) / 0.003, 2.0)) * step(abs(p.y - ICENTER.y), 0.22);
    return mix(col, u_accent, guide * u_reveal);
}

vec3 illKanizsa(vec2 p) {                               // el triangulo blanco no existe: lo inventa el cerebro
    vec2 v = p - ICENTER;
    float rot0 = u_actph * 0.12 * ((u_actp.y > 0.5) ? 1.0 : -1.0);
    vec3 col = u_tuna;
    float a = (1.0 - u_reveal) * 0.52;                  // semiangulo del bocado; al revelar se cierran las bocas
    for (int i = 0; i < 3; i++) {
        float th = rot0 + 1.5708 + float(i) * 2.0944;
        vec2 c = 0.20 * vec2(cos(th), sin(th));
        vec2 q = v - c;
        float dirA = atan(-c.y, -c.x);
        float dq = atan(q.y, q.x) - dirA;
        float ang = abs(atan(sin(dq), cos(dq)));
        float m = (1.0 - smoothstep(-0.002, 0.002, length(q) - 0.075)) * (1.0 - step(ang, a));
        col = mix(col, u_tunb, m);
    }
    return col;
}

vec3 illZollner(vec2 p) {                               // rayitas alternas hacen que las lineas largas parezcan inclinadas
    vec2 q = rot(p - ICENTER, 0.6);
    float s = 0.17;
    float row = floor(q.y / s + 0.5);
    float ly = q.y - row * s;                           // distancia con signo a la linea de la fila
    vec3 col = u_tunb;
    float line = 1.0 - smoothstep(0.005, 0.008, abs(ly));
    float dx = (fract(q.x / 0.07 + 0.25 * mod(row, 2.0)) - 0.5) * 0.07;
    vec2 lr = rot(vec2(dx, ly), (mod(row, 2.0) < 0.5) ? 0.75 : -0.75);
    float hatch = (1.0 - smoothstep(0.004, 0.007, abs(lr.y))) * (1.0 - smoothstep(0.036, 0.040, abs(lr.x)));
    col = mix(col, u_tuna, max(line, hatch));
    float guide = exp(-pow(abs(ly) / 0.0035, 2.0));
    return mix(col, u_accent, guide * u_reveal);
}

vec3 illusionScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / u_res.x;
    vec3 bg = background(px);
    vec3 c;
    if (u_kind == 0)      c = illOuchi(p);
    else if (u_kind == 1) c = illCafe(p);
    else if (u_kind == 2) c = illEbbinghaus(p, bg);
    else if (u_kind == 3) c = illScintillating(p);
    else if (u_kind == 4) c = illSpiral(p);
    else if (u_kind == 5) c = illMoire(p);
    else if (u_kind == 6) c = illHermann(p);
    else if (u_kind == 7) c = illMullerLyer(p);
    else if (u_kind == 8) c = illKanizsa(p);
    else                  c = illZollner(p);
    return timerBar(mix(bg, c, u_pop), px);
}

// ------------------------------------------------------------------ MODO 3: bucle perfecto
// Todo es periodico con periodo u_loopP: las fases usan multiplos ENTEROS de 2*PI.
vec3 loopScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / (0.5 * u_res.y);
    float ph = fract(u_time / u_loopP);
    float th = ph * TAU;
    float r = length(p) + 1e-4;
    vec3 col;

    if (u_loopkind == 0) {                                     // zoom poligonal sin fin
        float n = float(u_hooksides), an = PI / n;
        vec2 q = rot(p, th * u_lint.y / n + log(r) * (u_rnd.y - 0.5) * 3.0);
        float bn = mod(atan(q.x, q.y), 2.0 * an) - an;
        float gauge = length(q) * cos(bn) + 1e-4;
        float k = log(gauge) * 2.0 - ph * u_lint.x;
        float c = abs(edge(sin(k * TAU)) - edge(sin(atan(q.x, q.y) * n)));
        col = mix(u_tunb, u_tuna, c);
        col = mix(col, u_accent, 0.25 * (0.5 + 0.5 * sin(th * u_lint.z + log(gauge) * 5.0)) * c);
        col += u_tuna * exp(-r * 4.5) * 0.45;
    } else if (u_loopkind == 1) {                              // anillos de figuras orbitando
        col = mix(u_bg1, u_bg2, 0.5 + 0.5 * sin(r * 3.0 - th * u_lint.x));
        float a = atan(p.y, p.x);
        float px1 = 2.0 / u_res.y;
        for (int i = 0; i < 7; i++) {
            float fi = float(i);
            float R = 0.18 + fi * 0.17;
            float M = 4.0 + 2.0 * fi;
            float dir = (mod(fi, 2.0) < 0.5) ? 1.0 : -1.0;
            float rt = dir * th * (1.0 + mod(fi, 3.0));
            float an = TAU / M;
            float aa = mod(a - rt + an * 0.5, an) - an * 0.5;
            vec2 q = r * vec2(cos(aa), sin(aa)) - vec2(R, 0.0);
            float sz = 0.045 + 0.014 * sin(th * u_lint.z + fi);
            float d = shapeSD(rot(q, rt), sz / 0.36);
            vec3 sc = mix(u_tuna, u_accent, fi / 6.0);
            col += sc * 0.25 * exp(-max(d, 0.0) * 60.0);
            col = mix(col, sc, 1.0 - smoothstep(-px1, px1, d));
        }
    } else {                                                   // interferencia de ondas
        float a = atan(p.y, p.x);
        float n1 = floor(3.0 + u_rnd.x * 5.0), n2 = floor(2.0 + u_rnd.z * 6.0);
        float v = sin(r * 9.0 - th * u_lint.x) + sin(n1 * a + th * u_lint.y + r * 3.0)
                + sin(r * 6.0 + n2 * a - th * u_lint.z);
        float band = edge(sin(v * 3.5));
        col = mix(u_tunb, u_tuna, band);
        col = mix(col, u_accent, 0.3 * smoothstep(0.8, 1.0, sin(v * 1.1 + th)) * band);
        col += u_tuna * exp(-r * 5.0) * 0.4;
    }
    col *= 1.0 - 0.4 * smoothstep(0.8, 1.9, r);
    return col;
}

// ------------------------------------------------------------------ MODO 4: sincronizacion (pause game)
// La figura orbita/gira a velocidad extrema; u_tau = 0 SOLO en un frame (el del encaje exacto).
vec3 syncScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / u_res.x;
    vec3 col = background(px);
    float spd = 1.0 + (1.0 - u_delta);                 // mas rapido en los actos dificiles
    float a1 = (9.0 + 4.0 * u_actp.x) * spd;
    float a2 = a1 * 1.618 + 2.0;
    float a3 = (13.0 + 6.0 * u_actp.y) * spd;
    float a4 = a1 * 0.73;
    float s0 = 0.19 / 0.36;
    vec3 figc = hsv2rgb(vec3(u_hue, u_sv.x, 1.0));

    float dS = shapeSD(p - ICENTER, s0);               // silueta central
    col = mix(col, vec3(0.0), 0.6 * (1.0 - smoothstep(-0.002, 0.002, dS)) * u_pop);
    col = mix(col, vec3(1.0), exp(-pow(dS / 0.004, 2.0)) * 0.9 * u_pop);

    float err = 0.0;
    for (int k = 4; k >= 0; k--) {                     // k=0 figura; k>0 estela
        float tk = u_tau - float(k) * 0.011;
        vec2 off = vec2(0.30 * sin(a1 * tk), 0.27 * sin(a2 * tk));
        float ang = a3 * tk;
        float sc = (u_actp.x > 0.5) ? 1.0 + 0.7 * abs(sin(a4 * tk)) : 1.0;
        float d = shapeSD(rot(p - ICENTER - off, ang), s0 * sc * 0.96);
        float m = (1.0 - smoothstep(-0.0015, 0.0015, d)) * u_pop;
        float alpha = (k == 0) ? 1.0 : 0.16 * (1.0 - float(k) / 5.0);
        col = mix(col, figc, m * alpha);
        if (k == 0) err = length(off) + abs(ang) * 0.05 + abs(sc - 1.0) * 0.1;
    }
    float hit = 1.0 - smoothstep(0.004, 0.012, err);   // destello: encaje perfecto
    col = mix(col, u_accent, hit * 0.55 * (1.0 - smoothstep(-0.002, 0.002, dS)) * u_pop);
    col += u_accent * hit * exp(-pow(dS / 0.02, 2.0)) * 0.8;
    col += u_accent * u_reveal * exp(-pow(dS / 0.006, 2.0)) * 0.5;
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 5: ishihara (Voronoi + figura oculta)
const int SEG[10] = int[10](63, 6, 91, 79, 102, 109, 125, 7, 127, 111);
float sdSeg(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    return length(pa - ba * clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0));
}
float sdDigit(vec2 p, int d) {                         // digito de 7 segmentos, alto 1, ancho ~0.5
    int m = SEG[d];
    float r = 1e5;
    if ((m & 1) != 0)  r = min(r, sdSeg(p, vec2(-0.20, 0.45),  vec2(0.20, 0.45)));
    if ((m & 2) != 0)  r = min(r, sdSeg(p, vec2(0.25, 0.40),   vec2(0.25, 0.05)));
    if ((m & 4) != 0)  r = min(r, sdSeg(p, vec2(0.25, -0.05),  vec2(0.25, -0.40)));
    if ((m & 8) != 0)  r = min(r, sdSeg(p, vec2(-0.20, -0.45), vec2(0.20, -0.45)));
    if ((m & 16) != 0) r = min(r, sdSeg(p, vec2(-0.25, -0.05), vec2(-0.25, -0.40)));
    if ((m & 32) != 0) r = min(r, sdSeg(p, vec2(-0.25, 0.40),  vec2(-0.25, 0.05)));
    if ((m & 64) != 0) r = min(r, sdSeg(p, vec2(-0.20, 0.0),   vec2(0.20, 0.0)));
    return r - 0.085;
}
float numSD(vec2 q, int n) {                           // numero de 1-2 digitos, q en unidades de alto de digito
    q.y = -q.y;                                        // sdDigit usa y hacia arriba; la imagen usa y hacia abajo
    if (n >= 10) {
        int d1 = n / 10, d2 = n - 10 * d1;
        return min(sdDigit(q - vec2(-0.40, 0.0), d1), sdDigit(q - vec2(0.40, 0.0), d2));
    }
    return sdDigit(q, n);
}
float symbolSD(vec2 p) {                               // p relativo al centro del simbolo
    if (u_sym >= 0) {
        float H = 0.42;
        return numSD(p / H, u_sym) * H;
    }
    return shapeSDi(rot(p, u_actp.y * TAU), 0.30 / 0.36, u_actshape);
}

vec3 ishiScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / u_res.x;
    float cs = 0.032 + 0.016 * u_actp.x;               // tamaño de celda
    vec2 g = p / cs, ig = floor(g);
    float T = u_actph * (0.6 + 0.5 * u_speed);
    float best = 1e5;
    vec2 bc = vec2(0.0), bid = vec2(0.0);
    for (int j = -1; j <= 1; j++)
        for (int i = -1; i <= 1; i++) {
            vec2 id = ig + vec2(float(i), float(j));
            vec2 h = vec2(hash21(id + 1.7), hash21(id + 9.3));
            vec2 pt = id + 0.5 + 0.38 * sin(T * (0.6 + h.yx) + h * TAU);   // puntos que fluctuan
            float d = length(g - pt);
            if (d < best) { best = d; bc = pt; bid = id; }
        }
    float hr = hash21(bid + 3.1);
    float rr = 0.30 + 0.16 * hr + 0.04 * sin(T * 1.7 + hr * TAU);          // radio fluctuante
    float sdm = symbolSD(bc * cs - ICENTER);           // mascara evaluada en el centro de la celda
    bool inside = sdm < 0.0;
    float dEff = mix(u_delta, 1.0, u_reveal);          // al revelar, el contraste sube al maximo

    bool mono = u_sv.x < 0.01;
    float hn = hash21(bid + 7.7), vn = hash21(bid + 13.1);
    float vn2 = hash21(bid + floor(u_actph * 3.0) * 1.37);                 // ruido que se re-sortea 3x/s
    float hue = u_hue + (hn - 0.5) * 0.03;
    float val = u_sv.y * 0.9 + (mix(vn, vn2, 0.5) - 0.5) * 0.32;
    if (inside) {
        hue += 0.14 * dEff;
        if (mono) val += 0.35 * dEff;
    }
    vec3 gap = u_bg1 * 0.7;
    float aa = 0.05;
    vec3 col = mix(gap, hsv2rgb(vec3(hue, u_sv.x, clamp(val, 0.05, 1.0))), 1.0 - smoothstep(rr - aa, rr + aa, best));
    col = mix(gap, col, u_pop);
    col = mix(col, u_accent, exp(-pow(symbolSD(p - ICENTER) / 0.006, 2.0)) * u_reveal);
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 6: enjambre (particle tracker)
vec3 swarmScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / u_res.x;
    vec3 col = background(px);
    float s = u_actph;
    float pr = 0.026 * u_pop;
    vec3 white = mix(u_tuna, vec3(1.0), 0.45);
    vec3 red = vec3(1.0, 0.12, 0.08);
    vec2 tpos = vec2(0.0);
    for (int i = 0; i < 40; i++) {
        if (i >= u_n) break;
        vec4 a = u_pa[i], b = u_pb[i];
        vec2 pos = vec2(a.x * sin(a.z * s + b.x), -0.02 + a.y * sin(a.w * s + b.y));
        bool tgt = (i == 0);
        if (tgt) tpos = pos;
        float d = shapeSD(p - pos, pr / 0.36);
        float redk = tgt ? max(u_hl, u_reveal) : 0.0;
        float dim = tgt ? 1.0 : mix(1.0, 0.35, u_reveal);
        vec3 c = mix(white, red, redk) * dim;
        col += c * 0.10 * exp(-max(d, 0.0) * 45.0);
        col = mix(col, c, 1.0 - smoothstep(-0.0012, 0.0012, d));
    }
    float dist = length(p - tpos);
    float ring = exp(-pow((dist - (0.065 + 0.008 * sin(u_time * 9.0))) / 0.004, 2.0));
    float ripple = 0.0;
    for (int i = 0; i < 3; i++) {
        float ph = fract(u_revt * 0.7 + float(i) / 3.0);
        ripple += exp(-pow((dist - (0.06 + ph * 0.5)) / 0.008, 2.0)) * (1.0 - ph);
    }
    col += (red * ring + red * ripple * 0.5) * u_reveal;
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 7: ojo magico (autostereograma)
// Pasada 1 (u_pass=1): mapa de profundidad. La CPU integra 1/(P - k*d) por fila -> textura u_phi (fase en
// periodos). Pasada 2: patron de puntos periodico en la fase => el desplazamiento horizontal codifica la profundidad.
const vec2 ECENTER = vec2(0.0, -0.241);                // px.y = 700: por encima de los subtitulos
float depthAt(vec2 p) {
    float sd, bev = 0.07, dome = 0.16;
    if (u_sym >= 0) {                                                       // numero 3D (trazo mas fino: bisel y domo menores)
        float H = 0.36;
        sd = numSD((p - ECENTER) / H, u_sym) * H - 0.012;                  // trazo engrosado: mas profundidad util
        bev = 0.014;
        dome = 0.040;
    } else {
        sd = shapeSDi(p - ECENTER, 0.23 / 0.36, u_actshape);
    }
    if (u_actp.y > 0.5) return pow(clamp(-sd / dome, 0.0, 1.0), 0.55);    // domo
    return smoothstep(0.0, bev, -sd);                                       // meseta con bordes biselados
}
vec3 magicScene(vec2 px) {
    ivec2 ip = ivec2(px);
    float phi = texelFetch(u_phi, ip, 0).r;
    float dep = texelFetch(u_dep, ip, 0).r;
    float dotpx = u_dot;
    float Np = u_me.x / dotpx;
    phi += u_actph * 0.03 * (u_actp.x > 0.5 ? 1.0 : -1.0);               // el patron fluye (no rompe la profundidad)
    float cx = floor(fract(phi) * Np);
    float cy = floor(px.y / dotpx);
    float n = hash21(vec2(cx, cy) + u_rnd.x * 50.0);
    vec3 col = mix(u_tunb, u_tuna, step(0.5, n)) * (0.9 + 0.2 * hash21(vec2(cx, cy) + 3.3));
    col = mix(u_bg1, col, u_pop);
    // puntos guia (para vision paralela): separados exactamente por un periodo
    float g = min(length(px - vec2(0.5 * u_res.x - 0.5 * u_me.x, 350.0)), length(px - vec2(0.5 * u_res.x + 0.5 * u_me.x, 350.0)));
    col = mix(col, u_accent, (1.0 - smoothstep(10.0, 12.0, g)) * u_pop);
    col = mix(col, u_accent, 0.35 * smoothstep(0.02, 0.12, dep) * u_reveal);
    col = mix(col, u_accent, clamp(fwidth(dep) * 6.0, 0.0, 1.0) * u_reveal);
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 8: contraste simultaneo
vec3 contrastScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / u_res.x;
    vec2 uv = px / u_res;
    float tau = 1.0 - u_progress;                      // progreso de la busqueda 0..1
    float T = u_actph * (0.6 + 0.5 * u_actp.x);
    float A = 0.20 + 0.10 * (1.0 - u_delta);
    float L0 = 0.5, Lbg = L0, Lb1 = L0, Lb2 = L0;
    float side = (u_actp.x < 0.5) ? 1.0 : -1.0;        // +1: el lado izquierdo tiene el fondo oscuro
    float dirn = (u_actp.y >= 0.5) ? 1.0 : -1.0;       // +1: el bloque se aclara de verdad (variante 1)
    bool two = (u_kind >= 2);

    if (u_kind == 0) {                                 // bloque constante, el fondo cambia
        if (u_actp.y < 0.5) Lbg = L0 + A * sin(T * 1.2) + 0.30 * (uv.y - 0.5);
        else                Lbg = L0 + A * sin(T * 1.2) * (0.5 + smoothstep(0.0, 0.5, length(p - ICENTER))) + 0.10;
    } else if (u_kind == 1) {                          // el bloque cambia de verdad, el fondo cambia mas rapido
        Lb1 = L0 + dirn * 0.12 * tau;
        Lbg = L0 + dirn * 0.30 * tau + 0.30 * (uv.y - 0.5);
    } else {                                           // dos bloques sobre fondos opuestos
        float split = smoothstep(-0.03, 0.03, p.x);
        float darkSide = L0 - 0.27, lightSide = L0 + 0.27;
        Lbg = mix(side > 0.0 ? darkSide : lightSide, side > 0.0 ? lightSide : darkSide, split);
        float dl = 0.05 + 0.03 * (1.0 - u_delta);
        Lb1 = L0 - ((u_kind == 3 && side > 0.0) ? dl : 0.0);     // bloque izquierdo
        Lb2 = L0 - ((u_kind == 3 && side < 0.0) ? dl : 0.0);     // bloque derecho
    }
    Lbg = mix(Lbg, L0, u_reveal);                      // al revelar el fondo se iguala y deja ver la verdad

    float sat = u_sv.x * 0.55;
    vec3 col = hsv2rgb(vec3(u_hue, sat, clamp(Lbg, 0.02, 1.0)));
    float ring = 0.0;
    if (!two) {
        float sd = shapeSD(p - ICENTER, 0.27 / 0.36);
        col = mix(col, hsv2rgb(vec3(u_hue, sat, Lb1)), 1.0 - smoothstep(-0.002, 0.002, sd));
        ring = exp(-pow(sd / 0.003, 2.0));
    } else {
        float sdl = shapeSD(p - vec2(-0.21, ICENTER.y), 0.16 / 0.36);
        float sdr = shapeSD(p - vec2(0.21, ICENTER.y), 0.16 / 0.36);
        col = mix(col, hsv2rgb(vec3(u_hue, sat, Lb1)), 1.0 - smoothstep(-0.002, 0.002, sdl));
        col = mix(col, hsv2rgb(vec3(u_hue, sat, Lb2)), 1.0 - smoothstep(-0.002, 0.002, sdr));
        ring = max(exp(-pow(sdl / 0.003, 2.0)), exp(-pow(sdr / 0.003, 2.0)));
    }
    col = mix(col, u_accent, ring * smoothstep(0.4, 1.0, u_reveal));
    col = mix(background(px), col, u_pop);
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 9: conteo de figuras
vec3 countScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / u_res.x;
    vec3 col = background(px);
    float s = u_actph * (0.35 + 0.15 * (1.0 - u_delta));
    bool mono = u_sv.x < 0.01;
    int k = 0;
    for (int i = 0; i < 40; i++) {
        if (i >= u_n) break;
        vec4 a = u_pa[i], b = u_pb[i];
        vec2 pos = vec2(a.x * sin(a.z * s + b.x), -0.02 + a.y * sin(a.w * s + b.y));
        bool match = (u_cnt.x < 0.0 || abs(b.z - u_cnt.x) < 0.5) && (u_cnt.y < 0.0 || abs(b.w - u_cnt.y) < 0.02);
        float d = shapeSDi(p - pos, 0.036 / 0.36 * u_pop, int(b.z + 0.5));
        vec3 c = mono ? mix(u_tuna, vec3(1.0), 0.3) : hsv2rgb(vec3(b.w, 0.85, 0.95));
        float dim = match ? 1.0 : mix(1.0, 0.3, u_reveal);
        col += c * 0.08 * exp(-max(d, 0.0) * 40.0) * dim;
        col = mix(col, c * dim, 1.0 - smoothstep(-0.0012, 0.0012, d));
        if (match) {
            k++;
            float rg = exp(-pow((length(p - pos) - 0.052) / 0.003, 2.0));
            float lab = numSD((p - pos - vec2(0.0, -0.095)) / 0.05, k) * 0.05;
            col = mix(col, u_accent, rg * u_reveal);
            col = mix(col, vec3(1.0), (1.0 - smoothstep(-0.0015, 0.0015, lab)) * u_reveal);
        }
    }
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 10: retos de texto (el texto lo dibuja ASS)
// u_kind: 0 acertijo (signos de interrogacion) | 1 colores | 2 calculo (operadores) | 3 secuencia (digitos)
// u_q = (semialto de la tarjeta, centro y de la tarjeta) en unidades de ancho; el texto va dentro de la tarjeta.
float qmarkSD(vec2 q) {                                 // signo de interrogacion de trazos (q con y hacia abajo)
    q.y = -q.y;
    float d = sdSeg(q, vec2(-0.17, 0.10), vec2(-0.12, 0.21));
    d = min(d, sdSeg(q, vec2(-0.12, 0.21), vec2(0.0, 0.27)));
    d = min(d, sdSeg(q, vec2(0.0, 0.27), vec2(0.12, 0.21)));
    d = min(d, sdSeg(q, vec2(0.12, 0.21), vec2(0.17, 0.10)));
    d = min(d, sdSeg(q, vec2(0.17, 0.10), vec2(0.12, 0.0)));
    d = min(d, sdSeg(q, vec2(0.12, 0.0), vec2(0.0, -0.07)));
    d = min(d, sdSeg(q, vec2(0.0, -0.07), vec2(0.0, -0.15)));
    return min(d - 0.045, length(q - vec2(0.0, -0.27)) - 0.055);
}
float opSD(vec2 q, int k) {
    if (k == 0) return min(sdSeg(q, vec2(-0.16, 0.0), vec2(0.16, 0.0)), sdSeg(q, vec2(0.0, -0.16), vec2(0.0, 0.16))) - 0.045;
    if (k == 1) return sdSeg(q, vec2(-0.17, 0.0), vec2(0.17, 0.0)) - 0.045;
    return min(sdSeg(q, vec2(-0.12, -0.12), vec2(0.12, 0.12)), sdSeg(q, vec2(-0.12, 0.12), vec2(0.12, -0.12))) - 0.045;
}
vec3 textScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / u_res.x;
    vec3 col = background(px);
    float T = u_time * u_speed;
    vec2 cc = vec2(0.0, u_q.y);
    // resplandor central que respira
    col += u_accent * 0.10 * exp(-length((p - cc) * vec2(1.0, 0.8)) * 2.6) * (0.8 + 0.2 * sin(T * 1.3)) * u_pop;
    // poligonos concentricos girando (como antes, mas tenues)
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        float d = abs(shapeSD(rot(p - cc, T * (0.15 + 0.08 * fi) * ((i % 2 == 0) ? 1.0 : -1.0)), (0.30 + 0.17 * fi) / 0.36)) - 0.0015;
        col = mix(col, u_accent, (1.0 - smoothstep(0.0, 0.004, d)) * 0.14 * u_pop);
    }
    // simbolos del reto que suben flotando por detras de la tarjeta
    for (int i = 0; i < 18; i++) {
        float fi = float(i);
        float h1 = hash21(vec2(fi, 1.7)), h2 = hash21(vec2(fi, 9.1)), h3 = hash21(vec2(fi, 4.3));
        float sz = 0.05 + 0.08 * h3;
        float y = 0.95 - fract(h1 + T * (0.03 + 0.05 * h2)) * 1.9;
        vec2 q = rot((p - vec2((h2 - 0.5) * 1.0 + 0.03 * sin(T * 0.8 + fi), y)) / sz, (h1 - 0.5) * 0.9 + T * (h3 - 0.5) * 0.4);
        float d;
        vec3 c = mix(u_accent, u_tuna, 0.35 * h1);
        if (u_kind == 0)      d = qmarkSD(q * 1.6) / 1.6;
        else if (u_kind == 1) { d = length(q) - 0.30; c = hsv2rgb(vec3(h1, 0.75, 1.0)); }
        else if (u_kind == 2) d = opSD(q * 1.6, int(h3 * 2.99)) / 1.6;
        else                  d = numSD(q * 1.3, int(h2 * 9.99)) / 1.3;
        d *= sz;
        float a = (0.10 + 0.13 * h3) * u_pop;
        col += c * 0.05 * exp(-max(d, 0.0) * 45.0) * a * 4.0;
        col = mix(col, c, (1.0 - smoothstep(-0.002, 0.002, d)) * a);
    }
    // tarjeta de lectura
    float grow = 0.94 + 0.06 * u_pop;
    vec2 hs = vec2(0.47, u_q.x) * grow;
    vec2 dd = abs(p - cc) - hs + 0.045;
    float dc = length(max(dd, 0.0)) + min(max(dd.x, dd.y), 0.0) - 0.045;
    float inside = 1.0 - smoothstep(-0.003, 0.003, dc);
    col = mix(col, col * 0.30 + u_bg1 * 0.45, inside * 0.82 * u_pop);
    vec3 bcol = mix(u_accent, vec3(1.0), 0.45 * u_reveal);
    col += bcol * exp(-pow(dc / 0.0045, 2.0)) * (0.60 + 0.25 * sin(T * 2.0) + 0.5 * u_reveal) * u_pop;
    col += u_accent * 0.16 * exp(-max(dc, 0.0) * 28.0) * u_pop;
    // al revelar: ondas que salen de la tarjeta
    float rp = fract(u_revt * 0.9);
    col += u_accent * exp(-pow((dc - rp * 0.30) / 0.012, 2.0)) * (1.0 - rp) * u_reveal * 0.8;
    col *= 1.0 - 0.30 * smoothstep(0.35, 1.0, length(p * vec2(1.0, 0.62)));       // viñeta
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 11: vasos (¿donde esta la bola?)
// u_q = (numero de vasos, vaso que tapa la bola); u_pa[k] = (inicio, duracion, hueco A, hueco B) de cada intercambio;
// u_actp.x = instante en que aparecen los numeros de hueco. Cada vaso reconstruye su posicion a partir de la lista.
float cupSD(vec2 q) {                                  // vaso boca abajo (y hacia abajo): estrecho arriba, aro ancho abajo
    float hw = mix(0.048, 0.074, clamp((q.y + 0.085) / 0.17, 0.0, 1.0));
    vec2 d = vec2(abs(q.x) - hw + 0.008, abs(q.y) - 0.085 + 0.008);
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - 0.008;
}
float cupSlotX(float k, float nc) { return (k - 0.5 * (nc - 1.0)) * (nc > 3.5 ? 0.25 : 0.30); }

vec3 cupsScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / u_res.x;
    vec3 col = background(px);
    float nc = u_q.x, t = u_actph, CY = -0.15;
    const float KS = 1.2;                              // escala de los vasos
    int ball = int(u_q.y + 0.5);
    float finalSlot = 0.0;
    vec2 bpos = vec2(0.0);
    for (int c = 0; c < 5; c++) {
        if (float(c) >= nc) break;
        float sl = float(c);
        float x = cupSlotX(sl, nc), dy = 0.0;
        for (int i = 0; i < 40; i++) {
            if (i >= u_n) break;
            vec4 sw = u_pa[i];
            if (t < sw.x) break;
            float s = clamp((t - sw.x) / sw.y, 0.0, 1.0);
            bool isA = abs(sl - sw.z) < 0.1, isB = abs(sl - sw.w) < 0.1;
            if (!isA && !isB) continue;
            float to = isA ? sw.w : sw.z;
            if (s < 1.0) {                              // intercambio en curso: arco hacia delante / atras
                float e = s * s * (3.0 - 2.0 * s);
                x = mix(cupSlotX(sl, nc), cupSlotX(to, nc), e);
                dy = (isA ? 1.0 : -1.0) * 0.045 * sin(PI * s);
                break;
            }
            sl = to;
            x = cupSlotX(sl, nc);
        }
        bool isBall = (c == ball);
        float lift = isBall ? max(1.0 - smoothstep(1.2, 1.7, t), u_reveal) : 0.0;
        if (isBall) { finalSlot = sl; bpos = vec2(x, CY); }
        // sombra en el suelo
        vec2 sq = p - vec2(x, CY + 0.108 + dy * 0.4);
        col *= 1.0 - 0.35 * u_pop * exp(-(sq.x * sq.x / 0.0030 + sq.y * sq.y / 0.00016));
        if (isBall) {                                   // la bola, en el suelo bajo el vaso
            float db = length(p - vec2(x, CY + 0.066 + dy)) - 0.0336 * u_pop;
            vec3 bc = mix(vec3(1.0), u_accent, 0.35);
            col += bc * 0.25 * exp(-max(db, 0.0) * 30.0) * lift;
            col = mix(col, bc, 1.0 - smoothstep(-0.0015, 0.0015, db));
        }
        vec2 q = p - vec2(x, CY + dy - 0.13 * lift);
        float d = cupSD(q / (KS * max(u_pop, 0.05))) * KS * u_pop;
        float m = 1.0 - smoothstep(-0.0015, 0.0015, d);
        vec3 base = hsv2rgb(vec3(u_hue, u_sv.x * 0.9, 0.86));
        vec3 cc = base * (0.80 + 0.30 * (0.5 - q.y / (0.17 * KS)));
        cc += 0.22 * smoothstep(0.048, 0.074, q.y);                           // aro inferior mas claro
        cc += 0.20 * exp(-pow((q.x + 0.026) / 0.012, 2.0)) * step(q.y, 0.06); // brillo lateral
        float dim = isBall ? 1.0 : mix(1.0, 0.45, u_reveal);
        col = mix(col, cc * dim, m);
    }
    // aro y numeros de hueco (para responder 1, 2 o 3 en los comentarios)
    col += u_accent * exp(-pow((length(p - bpos - vec2(0.0, 0.03)) - 0.14) / 0.004, 2.0)) * u_reveal;
    float show = max(smoothstep(u_actp.x, u_actp.x + 0.3, t), u_reveal);
    for (int k = 0; k < 5; k++) {
        if (float(k) >= nc) break;
        vec2 nq = p - vec2(cupSlotX(float(k), nc), -0.426);
        float dn = numSD(nq / 0.055, k + 1) * 0.055;
        float isFinal = (abs(float(k) - finalSlot) < 0.1) ? u_reveal : 0.0;
        vec3 nc3 = mix(vec3(1.0), u_accent, isFinal);
        col = mix(col, vec3(0.0), (1.0 - smoothstep(-0.002, 0.012, dn)) * 0.5 * show);
        col = mix(col, nc3, (1.0 - smoothstep(-0.0015, 0.0015, dn)) * show);
    }
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 12: Simon (recuerda el orden)
// u_q = (periodo de cada destello, inicio); u_pa[k].x = pad que se enciende en el paso k; u_actp.x = paso por el que se
// pregunta (1..n). Al revelar se repite la secuencia mostrando el numero de paso y se marca el pad preguntado.
vec3 simonScene(vec2 px) {
    vec2 p = (px - 0.5 * u_res) / u_res.x;
    vec3 col = background(px);
    bool mono = u_sv.x < 0.01;
    int lit = -1, stepNo = 0;
    float amt = 0.0;
    float ft = (u_reveal < 0.01) ? (u_actph - u_q.y) / u_q.x : (u_revt - 0.25) / 0.42;
    if (ft >= 0.0 && ft < float(u_n)) {
        float fr = fract(ft);
        lit = int(u_pa[int(ft)].x + 0.5);
        amt = smoothstep(0.0, 0.06, fr) * (1.0 - smoothstep(0.62, 0.74, fr));
        if (u_reveal > 0.01) stepNo = int(ft) + 1;
    }
    int asked = int(u_pa[int(u_actp.x + 0.5) - 1].x + 0.5);
    for (int i = 0; i < 4; i++) {
        vec2 c = vec2((float(i % 2) - 0.5) * 0.25, -0.265 + (float(i / 2) - 0.5) * 0.25);
        vec2 q = p - c;
        float sz = 0.108 * u_pop;
        vec2 dd = abs(q) - vec2(sz - 0.02);
        float d = length(max(dd, 0.0)) + min(max(dd.x, dd.y), 0.0) - 0.02;
        float m = 1.0 - smoothstep(-0.0015, 0.0015, d);
        float a = (lit == i) ? amt : 0.0;
        vec3 base = mono ? vec3(0.62) : hsv2rgb(vec3(fract(u_hue + 0.25 * float(i)), 0.85, 1.0));
        vec3 pc = base * (0.30 + 0.85 * a);
        col += base * a * 0.40 * exp(-max(d, 0.0) * 22.0);
        col = mix(col, pc, m);
        int shown = (lit == i && stepNo > 0) ? stepNo : i + 1;
        float dn = numSD(q / 0.06, shown) * 0.06;
        col = mix(col, vec3(1.0), (1.0 - smoothstep(-0.0015, 0.0015, dn)) * (0.55 + 0.45 * a) * u_pop);
        float ring = exp(-pow((d - 0.012) / 0.005, 2.0)) * ((asked == i) ? u_reveal : 0.0);
        col = mix(col, u_accent, ring);
    }
    return timerBar(col, px);
}

// ------------------------------------------------------------------ MODO 13: numero distinto
// u_sym = digito base, u_actshape = digito distinto, u_target = celda del distinto.
vec3 digitsScene(vec2 px) {
    vec3 col = background(px);
    float cell = u_cell;
    vec2 origin = vec2(0.5 * (u_res.x - u_grid.x * cell), 0.5 * (u_res.y - u_grid.y * cell));
    vec2 g = (px - origin) / cell;
    vec2 id = floor(g);
    if (id.x >= 0.0 && id.x < u_grid.x && id.y >= 0.0 && id.y < u_grid.y) {
        vec2 f = fract(g) - 0.5;
        bool odd = all(equal(id, u_target));
        float h = hash21(id + u_rnd.w * 31.7);
        float T = u_time * u_speed;
        vec2 q = rot(f - 0.5 * motionOf(id), (h - 0.5) * 0.22 + 0.05 * sin(T * 1.3 + h * TAU));
        float H = 0.62 * u_pop;
        float d = numSD(q / max(H, 1e-3), odd ? u_actshape : u_sym) * H;
        float aa = 1.5 / u_cell;
        float m = 1.0 - smoothstep(-aa, aa, d);
        vec3 c = hsv2rgb(vec3(u_hue + (h - 0.5) * 0.01, u_sv.x, u_sv.y + (hash21(id + 9.1) - 0.5) * 0.05));
        float dim = odd ? 1.0 : mix(1.0, 0.35, u_reveal);
        col += hsv2rgb(vec3(u_hue, 0.6 * u_sv.x, 1.0)) * 0.14 * exp(-max(d, 0.0) * 16.0) * u_pop * dim;
        col = mix(col, c * dim, m);
    }
    vec2 tc = origin + (u_target + 0.5) * cell;
    float dist = length(px - tc) / cell;
    float ring = exp(-pow((dist - (0.50 + 0.03 * sin(u_time * 9.0))) / 0.018, 2.0));
    float ripple = 0.0;
    for (int i = 0; i < 3; i++) {
        float ph = fract(u_revt * 0.7 + float(i) / 3.0);
        ripple += exp(-pow((dist - (0.4 + ph * 1.6)) / 0.03, 2.0)) * (1.0 - ph);
    }
    col += (u_accent * ring + u_accent * ripple * 0.5) * u_reveal;
    return timerBar(col, px);
}

vec3 mainScene(vec2 px) {
    if (u_scene == 0) return anomalyScene(px);
    if (u_scene == 1) return illusionScene(px);
    if (u_scene == 3) return syncScene(px);
    if (u_scene == 4) return ishiScene(px);
    if (u_scene == 5) return swarmScene(px);
    if (u_scene == 6) return magicScene(px);
    if (u_scene == 7) return contrastScene(px);
    if (u_scene == 8) return countScene(px);
    if (u_scene == 9) return anomalyScene(px);
    if (u_scene == 10) return textScene(px);
    if (u_scene == 11) return cupsScene(px);
    if (u_scene == 12) return simonScene(px);
    if (u_scene == 13) return digitsScene(px);
    return loopScene(px);
}

void main() {
    vec2 px = gl_FragCoord.xy;
    if (u_pass == 1) {                                  // pasada de profundidad (sin dither)
        fragColor = vec4(vec3(depthAt((px - 0.5 * u_res) / u_res.x)), 1.0);
        return;
    }
    vec3 col;
    if (u_mix < 0.001)      col = hookScene(px);
    else if (u_mix > 0.999) col = mainScene(px);
    else                    col = mix(hookScene(px), mainScene(px), u_mix);
    col += (hash21(px + fract(u_time) * 97.0) - 0.5) / 255.0;   // dither anti-banding
    fragColor = vec4(col, 1.0);
}
