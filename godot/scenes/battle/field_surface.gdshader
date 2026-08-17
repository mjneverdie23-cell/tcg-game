shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never;

// The ground of one player's half, once their Environment is down. A wave
// sweeps out from where the card was laid and leaves the terrain behind it:
// lava for carnivores, turf for herbivores, sky for pterosaurs, sea for
// amphibians. Every pattern is procedural — there is no texture in this
// project, and a pattern that is generated re-tints and re-scales for free.
//
// The maths here was prototyped and rendered as images before being written
// as GLSL, so the frequencies and thresholds are the ones that were actually
// looked at rather than guessed.

uniform int theme : hint_range(0, 3) = 0;
// Where the card landed, in the plane's own XZ space.
uniform vec2 origin = vec2(0.0, 0.0);
uniform vec2 plane_size = vec2(11.0, 3.25);
// 0 = nothing revealed, 1 = the whole half.
uniform float progress : hint_range(0.0, 1.0) = 0.0;
uniform vec3 rim_color : source_color = vec3(1.0, 0.7, 0.28);
uniform float surface_alpha : hint_range(0.0, 1.0) = 0.88;
// How far past the far corner the wave front travels, and how soft it is.
uniform float reach = 12.5;
uniform float softness = 0.9;
uniform float rim_width = 1.1;

varying vec2 plane_xz;

const int THEME_LAVA = 0;
const int THEME_GRASS = 1;
const int THEME_WIND = 2;
const int THEME_OCEAN = 3;


float hash2(vec2 p) {
	return fract(sin(p.x * 127.1 + p.y * 311.7) * 43758.5453123);
}


float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = p - i;
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash2(i);
	float b = hash2(i + vec2(1.0, 0.0));
	float c = hash2(i + vec2(0.0, 1.0));
	float d = hash2(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}


// Normalised to 0..1. Un-normalised fbm never reaches its extremes, which
// quietly ruins every threshold taken against it.
float fbm(vec2 p) {
	float total = 0.0;
	float amp = 0.5;
	float norm = 0.0;
	for (int i = 0; i < 4; i++) {
		total += amp * value_noise(p);
		norm += amp;
		p *= 2.0;
		amp *= 0.5;
	}
	return total / norm;
}


// Dark rock cut by thin glowing cracks. The cracks are the zero crossings
// of a noise field, so a high power on (1 - |2f-1|) leaves veins rather
// than molten ground.
vec3 lava(vec2 uv, float t) {
	vec2 p = uv * 8.0;
	float flow = fbm(p + vec2(t * 0.10, -t * 0.04));
	float ridge = 1.0 - abs(flow * 2.0 - 1.0);
	float veins = pow(ridge, 16.0);
	float glow = pow(ridge, 4.0);
	float crust = fbm(p * 2.6);
	vec3 base = mix(vec3(0.114, 0.043, 0.027), vec3(0.251, 0.125, 0.102), crust);
	base = mix(base, vec3(0.420, 0.184, 0.086), clamp(glow * 0.5, 0.0, 1.0));
	vec3 hot = mix(vec3(1.0, 0.353, 0.078), vec3(1.0, 0.878, 0.541),
			clamp(veins * 1.4, 0.0, 1.0));
	return mix(base, hot, clamp(veins * 1.2, 0.0, 1.0));
}


// Turf: short blades in clumps. The vertical term cuts each blade into a
// tuft, without which the comb reads as corduroy.
vec3 grass(vec2 uv, float t) {
	float loam = fbm(uv * 6.0);
	float clump = fbm(uv * 13.0);
	float sway = sin(uv.y * 4.0 + t * 0.9) * 0.04;
	float scatter = value_noise(vec2(uv.x * 34.0, uv.y * 26.0));
	float comb = sin((uv.x + sway) * 460.0 + scatter * 11.0);
	float tuft = sin(uv.y * 150.0 + scatter * 7.0);
	float blade = smoothstep(0.55, 1.0, comb) * smoothstep(-0.2, 0.9, tuft);
	vec3 base = mix(vec3(0.067, 0.188, 0.102), vec3(0.169, 0.420, 0.169), loam);
	base = mix(base, vec3(0.094, 0.251, 0.114), smoothstep(0.55, 1.0, 1.0 - clump) * 0.7);
	vec3 lit = mix(base, vec3(0.325, 0.627, 0.267), clamp(blade, 0.0, 1.0) * 0.85);
	float tall = blade * smoothstep(0.6, 1.0, clump);
	return mix(lit, vec3(0.580, 0.831, 0.396), clamp(tall, 0.0, 1.0) * 0.9);
}


// Streaked air over cloud. Two streak layers at different speeds slide over
// each other, which is what makes still air read as moving.
vec3 wind(vec2 uv, float t) {
	float streak = fbm(vec2(uv.x * 4.0 - t * 0.60, uv.y * 22.0));
	float gust = fbm(vec2(uv.x * 7.5 - t * 1.05, uv.y * 34.0));
	float cloud = fbm(vec2(uv.x * 2.6 - t * 0.14, uv.y * 4.2));
	vec3 sky = mix(vec3(0.173, 0.290, 0.490), vec3(0.427, 0.561, 0.769),
			smoothstep(0.25, 0.85, cloud));
	vec3 body = mix(sky, vec3(0.804, 0.863, 0.961), smoothstep(0.60, 0.86, cloud) * 0.85);
	body = mix(body, vec3(1.0), smoothstep(0.78, 0.95, cloud) * 0.7);
	float bands = smoothstep(0.58, 0.92, streak) * 0.7 + smoothstep(0.70, 0.97, gust) * 0.55;
	return mix(body, vec3(0.957, 0.976, 1.0), clamp(bands, 0.0, 1.0) * 0.75);
}


// Swell rolling in depth, so the ridges run across the table towards the
// player rather than slicing it diagonally.
vec3 ocean(vec2 uv, float t) {
	float chop = fbm(vec2(uv.x * 7.0 + t * 0.20, uv.y * 7.0));
	float long_swell = sin(uv.y * 15.0 + uv.x * 1.6 + t * 1.15 + chop * 1.4);
	float short_swell = sin(uv.y * 27.0 - uv.x * 2.4 - t * 1.75 + chop * 1.9);
	float height = long_swell * 0.65 + short_swell * 0.35;
	float depth = smoothstep(-1.1, 1.1, height);
	vec3 base = mix(vec3(0.024, 0.141, 0.247), vec3(0.086, 0.408, 0.627), depth);
	base = mix(base, vec3(0.169, 0.576, 0.784), smoothstep(0.3, 1.0, depth) * 0.5);
	float crest = smoothstep(0.93, 1.0, long_swell) * 0.75
			+ smoothstep(0.96, 1.0, short_swell) * 0.45;
	return mix(base, vec3(0.875, 0.957, 1.0), clamp(crest, 0.0, 1.0));
}


void vertex() {
	// Model space, not UV: the distance the wave has travelled is a real
	// distance in table units, and this way nothing depends on how the mesh
	// happens to lay its UVs out.
	plane_xz = VERTEX.xz;
}


void fragment() {
	vec2 uv = plane_xz / plane_size + vec2(0.5);
	float t = TIME;
	vec3 color;
	if (theme == THEME_LAVA) {
		color = lava(uv, t);
	} else if (theme == THEME_GRASS) {
		color = grass(uv, t);
	} else if (theme == THEME_WIND) {
		color = wind(uv, t);
	} else {
		color = ocean(uv, t);
	}

	float d = distance(plane_xz, origin);
	float front = progress * reach;
	float wave = smoothstep(front, front - softness, d);
	// The rim rides the wave front and is gone once the sweep finishes.
	float rim = smoothstep(rim_width, 0.0, abs(d - front)) * (1.0 - step(0.999, progress));
	color = mix(color, rim_color, clamp(rim * 0.85, 0.0, 1.0));

	ALBEDO = color;
	ALPHA = clamp(wave, 0.0, 1.0) * surface_alpha;
}
