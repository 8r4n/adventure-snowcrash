shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Original ground blend (#159 · Refs #163 · Refs #141).
// World-space noise layers primary + secondary + optional rubble so AOI tiles
// don't read as flat Catppuccin slabs. Shared mats — no per-tile bake.
// Original shader — not third-party demo IP.

uniform vec4 albedo_tint : source_color = vec4(0.45, 0.46, 0.52, 1.0);
uniform vec4 blend_tint : source_color = vec4(0.32, 0.34, 0.38, 1.0);
uniform vec4 rubble_tint : source_color = vec4(0.28, 0.24, 0.2, 1.0);
uniform vec4 emission_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float emission_energy : hint_range(0.0, 4.0) = 0.0;
uniform float metallic : hint_range(0.0, 1.0) = 0.08;
uniform float roughness : hint_range(0.0, 1.0) = 0.72;
uniform vec2 world_uv_scale = vec2(0.42, 0.42);
uniform float blend_strength : hint_range(0.0, 1.0) = 0.55;
uniform float rubble_mix : hint_range(0.0, 1.0) = 0.18;
uniform float wear : hint_range(0.0, 1.0) = 0.35;
uniform bool use_blend = true;
uniform bool use_normal = true;
uniform bool use_alpha = false;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D blend_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D rubble_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;

varying vec3 world_pos;

float hash21(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 wuv = world_pos.xz * world_uv_scale;
	float n = value_noise(wuv * 1.6);
	float n2 = value_noise(wuv * 4.1 + 19.0);
	float n3 = value_noise(wuv * 9.0 + 41.0);

	vec3 a = texture(albedo_tex, wuv).rgb * albedo_tint.rgb;
	vec3 b = texture(blend_tex, wuv * 1.15 + 0.17).rgb * blend_tint.rgb;
	vec3 r = texture(rubble_tex, wuv * 1.7 + 0.33).rgb * rubble_tint.rgb;

	float mix_w = 0.0;
	if (use_blend) {
		mix_w = smoothstep(0.32, 0.68, n) * blend_strength;
		mix_w = clamp(mix_w + (n2 - 0.5) * wear * 0.35, 0.0, 1.0);
	}
	vec3 col = mix(a, b, mix_w);

	float rub = 0.0;
	if (use_blend && rubble_mix > 0.001) {
		rub = smoothstep(0.55, 0.82, n3) * rubble_mix;
		col = mix(col, r, rub);
	}

	float crack = step(0.965, abs(fract(wuv.x * 3.0 + n2) - 0.5) * 2.0);
	crack = max(crack, step(0.97, abs(fract(wuv.y * 2.7 + n) - 0.5) * 2.0));
	col *= 1.0 - crack * 0.18 * wear;

	ALBEDO = col;
	METALLIC = clamp(metallic + rub * 0.15, 0.0, 1.0);
	ROUGHNESS = clamp(roughness - mix_w * 0.08 + rub * 0.12, 0.08, 1.0);
	AO = clamp(0.72 + n2 * 0.22 - rub * 0.15, 0.25, 1.0);

	if (use_normal && use_blend) {
		vec3 sampled = texture(normal_tex, wuv).xyz;
		vec2 d = vec2(dFdx(mix_w + rub), dFdy(mix_w + rub));
		vec3 proc_n = normalize(vec3(-d.x * 1.8, -d.y * 1.8, 0.55));
		NORMAL_MAP = mix(proc_n * 0.5 + 0.5, sampled, 0.55);
		NORMAL_MAP_DEPTH = 0.45;
	}

	EMISSION = emission_color.rgb * emission_energy * (0.75 + mix_w * 0.35);

	if (use_alpha) {
		ALPHA = albedo_tint.a;
	}
}
