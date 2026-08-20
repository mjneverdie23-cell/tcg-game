shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never;

// The outline that marks a place on the table — a slot for a card, or the
// footprint of a pile. It has to read on bare table and on bright lava
// alike, which a flat translucent wash cannot do: 6% white is invisible
// over glowing rock and barely there over dark blue. So the marker is a
// drawn frame instead — a bright stroke for light against dark ground, and
// a dark wash inside it for contrast against bright ground.
//
// Distances are in table units rather than UV, so one shader serves quads
// of different shapes without the corner radius going oval.

uniform vec3 stroke_color : source_color = vec3(0.96, 0.725, 0.259);
// 0 = resting outline, 1 = fully lit. Everything else is interpolated.
uniform float lit : hint_range(0.0, 1.0) = 0.0;
uniform vec2 quad_size = vec2(0.954, 1.336);
uniform float corner = 0.075;
uniform float border = 0.022;
uniform float rest_stroke : hint_range(0.0, 1.0) = 0.40;
uniform float lit_stroke : hint_range(0.0, 1.0) = 1.0;
uniform float rest_fill : hint_range(0.0, 1.0) = 0.17;
uniform float lit_fill : hint_range(0.0, 1.0) = 0.30;


// Signed distance to a rounded rectangle: negative inside, zero on the edge.
float rounded_box(vec2 p, vec2 half_size, float radius) {
	vec2 q = abs(p) - half_size + vec2(radius);
	return min(max(q.x, q.y), 0.0) + length(max(q, vec2(0.0))) - radius;
}


void fragment() {
	vec2 p = (UV - vec2(0.5)) * quad_size;
	float sdf = rounded_box(p, quad_size * 0.5, corner);
	float aa = fwidth(sdf) * 1.5 + 0.0005;
	float line = smoothstep(border + aa, border - aa, abs(sdf));
	float inside = smoothstep(aa, -aa, sdf);
	float wash = clamp(inside - line, 0.0, 1.0);

	ALBEDO = mix(vec3(0.016, 0.024, 0.055), stroke_color, line);
	ALPHA = line * mix(rest_stroke, lit_stroke, lit)
			+ wash * mix(rest_fill, lit_fill, lit);
}
