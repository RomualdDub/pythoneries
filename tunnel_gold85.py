# =================================================================
# CONFIGURATION GOLD 8.5 - CRYSTAL EDITION (ÉQUILIBRE LUMINEUX)
# =================================================================
# Signature : .·:*¨ ¨*:·. - TUNNEL CRYSTAL - .·:*¨ ¨*:·.
# =================================================================

import pygame
import moderngl
import numpy as np
import os
import random

WIDTH, HEIGHT = 1280, 720
COLOR_FILE, BUMP_FILE, SPEC_FILE = "texture_color.png", "texture_bump.png", "texture_spec.png"

def generate_textures():
    """Génère des briques 4x8 avec grain cristallin et brillance équilibrée."""
    for f in [COLOR_FILE, BUMP_FILE, SPEC_FILE]:
        if os.path.exists(f): os.remove(f)

    pygame.init()
    size = 2048
    color_s, bump_s, spec_s = [pygame.Surface((size, size)) for _ in range(3)]
    color_s.fill((10, 15, 10))
    bump_s.fill((10, 10, 10))
    spec_s.fill((20, 20, 20))

    rows, cols = 4, 8
    b_w, b_h = size // cols, size // rows

    for r in range(rows):
        for c in range(cols):
            x, y = c * b_w, r * b_h
            rect = (x + 6, y + 6, b_w - 12, b_h - 12)

            bv = random.randint(30, 50)
            pygame.draw.rect(color_s, (bv - 5, bv + 10, bv - 2), rect)

            sv = random.randint(35, 45)
            pygame.draw.rect(spec_s, (sv, sv, sv), rect)
            for _ in range(1800):
                gx, gy = random.randint(x + 8, x + b_w - 16), random.randint(y + 8, y + b_h - 16)
                g_val = random.randint(160, 240)
                spec_s.set_at((gx, gy), (g_val, g_val, g_val))

            base_h = random.randint(30, 40)
            for i in range(10):
                v = min(base_h + i * 18, 255)
                m = 6 + i * 3
                pygame.draw.rect(bump_s, (v, v, v), (x + m, y + m, b_w - m * 2, b_h - m * 2))

    [pygame.image.save(s, f) for s, f in zip([color_s, bump_s, spec_s], [COLOR_FILE, BUMP_FILE, SPEC_FILE])]
    pygame.quit()

VERTEX_SHADER = """
#version 330
in vec2 in_vert;
void main() { gl_Position = vec4(in_vert, 0.0, 1.0); }
"""

FRAGMENT_SHADER = """
#version 330
uniform sampler2D u_texColor, u_texBump, u_texSpec;
uniform float u_time;
uniform vec2 u_res;
out vec4 f_color;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i + vec2(0,0)), hash(i + vec2(1,0)), u.x),
               mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    vec2 shift = vec2(100.0);
    for(int i=0; i<8; i++) {
        v += a * noise(p);
        p = p * 2.1 + shift;
        a *= 0.5;
    }
    return v;
}

float map(vec3 p) {
    p.x += sin(p.z * 0.3 + u_time * 0.5) * 0.4;
    p.y += cos(p.z * 0.2 + u_time * 0.3) * 0.3;
    float d = noise(normalize(p.xy) * 2.0 + p.z * 0.5) * 0.04;
    return -(length(p.xy) - (1.1 + d));
}

vec3 getNormal(vec3 p, vec2 uv) {
    vec2 e = vec2(0.002, 0.0); 
    vec3 n = normalize(vec3(map(p+e.xyy)-map(p-e.xyy), map(p+e.yxy)-map(p-e.yxy), map(p+e.yyx)-map(p-e.yyx)));
    float val = texture(u_texBump, uv).r;
    float valX = texture(u_texBump, uv+vec2(e.x, 0.0)).r;
    float valY = texture(u_texBump, uv+vec2(0.0, e.x)).r;
    vec3 bumpN = normalize(vec3((val-valX)*0.8, (val-valY)*0.8, 0.2));
    return normalize(n + bumpN);
}

void main() {
    vec2 screen_uv = gl_FragCoord.xy / u_res.xy;
    vec2 uv_s = (gl_FragCoord.xy - 0.5 * u_res.xy) / u_res.y;
    float r = sin(u_time * 0.4) * 0.5;
    uv_s *= mat2(cos(r), -sin(r), sin(r), cos(r));

    vec3 ro = vec3(-sin(u_time * 0.45) * 0.2, -cos(u_time * 0.3) * 0.15, u_time * 1.5);
    vec3 rd = normalize(vec3(uv_s, 1.5));

    float t = 0.0;
    for(int i = 0; i < 95; i++) {
        float d = map(ro + rd * t);
        if(d < 0.001 || t > 20.0) break;
        t += d * 0.5;
    }

    vec3 paleEmerald = vec3(0.5, 0.7, 0.6) * 2.2;

    if(t < 20.0) {
        vec3 p = ro + rd * t;
        float angle = atan(p.y, p.x) / 6.2831853; 
        vec2 uv_tex = vec2(angle * 8.0, p.z * 1.2);
        vec3 n = getNormal(p, uv_tex);

        float bVal = texture(u_texBump, uv_tex).r;
        float sMap = texture(u_texSpec, uv_tex).r;
        float shadowRelief = smoothstep(0.15, 0.8, bVal);

        vec3 albedo = texture(u_texColor, uv_tex).rgb * 20.0;
        float dirty = pow(fbm(uv_tex * 0.7), 2.0) * 1.2;
        albedo = mix(albedo, albedo * 0.05, clamp(dirty, 0.0, 1.0));

        vec3 lPos = ro + vec3(0.6 * sin(u_time), 0.4 * cos(u_time), 0.5);
        vec3 lDir = normalize(lPos - p);

        float lightDistanceFactor = smoothstep(-0.2, 2.5, t); 
        float diff = max(dot(n, lDir), 0.0) * (0.3 + 0.7 * shadowRelief);
        diff *= lightDistanceFactor;

        float specInt = mix(0.01, 1.0, sMap) * shadowRelief; 
        specInt *= mix(1.0, 0.05, clamp(dirty, 0.0, 1.0));
        float spec = pow(max(dot(rd, reflect(-lDir, n)), 0.0), 32.0) * specInt;
        spec *= lightDistanceFactor;

        // --- AMBIENT RÉÉQUILIBRÉ ---
        vec3 sCol = vec3(0.9, 1.0, 0.95) * spec * 4.5;
        vec3 ambient = (albedo * 0.025 * shadowRelief); 
        vec3 skyLight = vec3(0.02, 0.03, 0.02) * albedo;

        vec3 col = (albedo * diff * 1.0) + sCol + ambient + skyLight;
        f_color = vec4(mix(col, paleEmerald, smoothstep(6.0, 18.0, t)), 1.0);
    } else { 
        f_color = vec4(paleEmerald, 1.0); 
    }

    f_color.rgb = clamp((f_color.rgb*(2.51*f_color.rgb+0.03))/(f_color.rgb*(2.43*f_color.rgb+0.59)+0.14), 0.0, 1.0) * 1.1;
    f_color.rgb *= pow(16.0 * screen_uv.x * screen_uv.y * (1.0-screen_uv.x) * (1.0-screen_uv.y), 0.05);
}
"""

def main():
    generate_textures()
    pygame.init()
    pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
    pygame.display.set_caption(".·:*¨ ¨*:·. - CRYSTAL EQUILIBRIUM - .·:*¨ ¨*:·.")
    ctx = moderngl.create_context()
    prog = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER)

    def load_t(path, unit):
        img = pygame.image.load(path).convert()
        t = ctx.texture(img.get_size(), 3, pygame.image.tostring(img, "RGB", 1))
        t.repeat_x = t.repeat_y = True
        t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        t.build_mipmaps()
        t.use(unit)
        return t

    load_t(COLOR_FILE, 0); load_t(BUMP_FILE, 1); load_t(SPEC_FILE, 2)
    prog['u_texColor'], prog['u_texBump'], prog['u_texSpec'] = 0, 1, 2
    vao = ctx.vertex_array(prog, [(ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], 'f4')), '2f', 'in_vert')])

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT: return
        prog['u_time'].write(np.array([pygame.time.get_ticks() / 1000.0], 'f4'))
        prog['u_res'].write(np.array([float(pygame.display.get_window_size()[0]), float(pygame.display.get_window_size()[1])], 'f4'))
        ctx.clear(0, 0, 0); vao.render(moderngl.TRIANGLE_STRIP); pygame.display.flip()

if __name__ == "__main__":
    main()