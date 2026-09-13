shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Original Catppuccin trim / PBR recolor (#156 · Refs #163 · Refs #141).
// Spirit: Steam-screenshot-readable panels (trim + ORM + emission) like a real 3D
// Godot product. Original shader — not third-party demo IP.

uniform vec4 albedo_tint : source_color = vec4(0.72, 0.76, 0.82, 1.0);
uniform vec4 emission_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float emission_energy : hint_range(0.0, 8.0) = 0.0;
uniform float metallic : hint_range(0.0, 1.0) = 0.22;
uniform float roughness : hint_range(0.0, 1.0) = 0.42;
uniform vec2 uv_scale = vec2(2.0, 2.0);
uniform float trim_mix : hint_range(0.0, 1.0) = 0.62;
uniform float panel_freq : hint_range(1.0, 16.0) = 4.0;
uniform float grout : hint_range(0.02, 0.28) = 0.08;
uniform bool use_normal = true;
uniform bool use_orm = true;
uniform bool use_alpha = false;
uniform bool use_albedo_tex = true;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap, repeat_enable;

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

void fragment() {
	vec2 uv = UV * uv_scale;
	vec2 cell = fract(uv * panel_freq);
	vec2 edge = min(cell, vec2(1.0) - cell);
	float e = min(edge.x, edge.y);
	float grout_mask = step(grout, e);
	float bevel = smoothstep(0.0, grout * 2.2, e);
	float n = value_noise(uv * 7.0) * 0.10 + value_noise(uv * 28.0) * 0.05;

	float tex_luma = 0.72;
	if (use_albedo_tex) {
		vec4 tex = texture(albedo_tex, uv);
		tex_luma = dot(tex.rgb, vec3(0.299, 0.587, 0.114));
	}
	float proc = clamp(0.28 + bevel * 0.62 + n, 0.08, 1.0);
	float pattern = mix(proc, tex_luma, 0.55);
	pattern = mix(0.92, pattern, trim_mix);

	ALBEDO = albedo_tint.rgb * pattern;

	float met = metallic;
	float rou = roughness;
	float ao = mix(0.48, 1.0, grout_mask);
	if (use_orm) {
		vec4 orm = texture(orm_tex, uv);
		ao *= orm.r;
		rou = mix(rou, orm.g, 0.7);
		met = mix(met, orm.b, 0.55);
	}
	METALLIC = clamp(met, 0.0, 1.0);
	ROUGHNESS = clamp(rou + (1.0 - bevel) * 0.12, 0.04, 1.0);
	AO = clamp(ao, 0.15, 1.0);

	if (use_normal) {
		vec3 sampled = texture(normal_tex, uv).xyz;
		vec2 d = vec2(dFdx(bevel), dFdy(bevel));
		vec3 proc_n = normalize(vec3(-d.x * 2.4, -d.y * 2.4, 0.45));
		NORMAL_MAP = mix(proc_n * 0.5 + 0.5, sampled, 0.72);
		NORMAL_MAP_DEPTH = 0.62;
	}

	// Neon edge lift so Catppuccin emission reads in stills without extra Omnis.
	float edge_boost = mix(0.72, 1.22, bevel);
	EMISSION = emission_color.rgb * emission_energy * pattern * edge_boost;

	if (use_alpha) {
		ALPHA = albedo_tint.a;
	}
}
