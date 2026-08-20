"""Compiles a Godot spatial shader with a real GLSL compiler.

Godot's shading language is GLSL with its own preamble and a set of
built-ins, and headless Godot never compiles shaders at all — a broken one
loads without a word. This rewrites the Godot-specific surface into plain
GLSL 4.50 and hands the body, untouched, to glslangValidator. Anything
wrong with the actual maths — a type mismatch, a missing argument, an
undeclared name — is caught there.
"""
import re
import subprocess
import sys

BUILTINS_VERTEX = """
vec3 VERTEX = vec3(0.0);
"""

BUILTINS_FRAGMENT = """
vec3 VERTEX = vec3(0.0);
vec2 UV = vec2(0.0);
float TIME = 0.0;
vec3 ALBEDO = vec3(0.0);
float ALPHA = 0.0;
"""


def to_glsl(source: str, stage: str) -> str:
    lines = []
    for line in source.split("\n"):
        stripped = line.strip()
        if stripped.startswith("shader_type") or stripped.startswith("render_mode"):
            continue
        # Godot uniform hints have no GLSL equivalent; the type is what matters.
        line = re.sub(r"^(\s*uniform\s+[\w]+\s+\w+)\s*:\s*[^=;]+", r"\1", line)
        # `varying` is Godot's name for a vertex -> fragment channel.
        if stripped.startswith("varying "):
            keyword = "out" if stage == "vert" else "in"
            line = line.replace("varying ", keyword + " ", 1)
        lines.append(line)
    body = "\n".join(lines)

    # Keep only the stage being compiled, so `VERTEX` means the right thing.
    drop = "fragment" if stage == "vert" else "vertex"
    body = re.sub(r"\nvoid %s\(\)\s*\{.*?\n\}\n" % drop, "\n", body, flags=re.S)
    body = body.replace("void vertex()", "void godot_vertex()")
    body = body.replace("void fragment()", "void godot_fragment()")

    builtins = BUILTINS_VERTEX if stage == "vert" else BUILTINS_FRAGMENT
    entry = "godot_vertex" if stage == "vert" else "godot_fragment"
    return "#version 450 core\n%s\n%s\nvoid main() { %s(); }\n" % (
        builtins, body, entry)


def main(path: str) -> int:
    source = open(path).read()
    failed = 0
    print("== %s" % path)
    for stage in ("vert", "frag"):
        # A Godot shader may define only one of the two stages; the engine
        # fills the other in, and there is nothing here to check.
        entry = "vertex" if stage == "vert" else "fragment"
        if ("void %s(" % entry) not in source:
            print("%s stage: not defined" % stage)
            continue
        glsl = "/tmp/godot_shader_check.%s" % stage
        open(glsl, "w").write(to_glsl(source, stage))
        result = subprocess.run(
            ["glslangValidator", glsl], capture_output=True, text=True)
        ok = result.returncode == 0
        print("%s stage: %s" % (stage, "OK" if ok else "FAILED"))
        if not ok:
            failed = 1
            print(result.stdout.strip())
            print(result.stderr.strip())
    return failed


if __name__ == "__main__":
    targets = sys.argv[1:]
    if not targets:
        import glob
        targets = sorted(glob.glob("godot/**/*.gdshader", recursive=True))
    sys.exit(max(main(t) for t in targets) if targets else 0)
