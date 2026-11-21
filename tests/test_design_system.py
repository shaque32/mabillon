"""The app's design system holds: every rule in ui/theme.py and ui/css/ draws from the tokens.

One spacing scale, one type scale, eleven colors, one radius, no gradients and no shadows
(TOKENS_CSS in ui/theme.py). This test reads the stylesheet the app puts on every page and fails
on any value from outside those tokens, so a new off-scale margin or a twelfth color cannot land
quietly. It also holds the colors to their jobs: every text and fill pair the stylesheet sets
passes WCAG AA, and the support green reaches only the marks it was signed off for, never a
model's label or the AI reviewer's acceptance. It checks the CSS text only: no case, no model, no
server.
"""

from __future__ import annotations

import re
from pathlib import Path

from ui.css import PAGE_CSS
from ui.theme import MARK, THEME_CSS, TOKENS_CSS

ROOT = Path(__file__).resolve().parents[1]

COLORS = {
    "--ink": "#141414",
    "--muted": "#5f5a51",
    "--paper": "#f7f5f0",
    "--line": "#dedad0",
    "--accent": "#1d3557",
    "--accent-wash": "#e4eaf2",
    "--support": "#2f5d43",
    "--support-wash": "#e6eee8",
    "--signal": "#9a3a2c",
    "--signal-wash": "#f4e5e1",
    "--quote": "#f3e3a6",
}
# Colors that carry text, and the fills text sits on. Every pair must pass WCAG AA for body text.
TEXT_COLORS = ("--ink", "--muted", "--accent", "--support", "--signal")
AA = 4.5
# The only places the support green may show: a Supported verdict an expert confirmed (v-sup),
# one that rests on the code checks (v-supchk) or on counsel's review (v-supcou), the counts and
# headings of the Supported group (t-sup, #sup), an assumption the records cover (li.ok .said,
# with the AI-reviewed tier turned back to muted) and the Timeline's code-compared matches
# (chip.ok, d-ok). A new use is a decision about what may look supported: add it here on purpose.
SUPPORT_HOOKS = re.compile(
    r"\.v-sup(?![a-z])|\.v-supchk(?![a-z])|\.v-supcou(?![a-z])|\.t-sup(?![a-z])|#sup(?![a-z])"
    r"|li\.ok \.said|\.chip\.ok(?![a-z])|\.d-ok(?![a-z])"
)
# Marks that must never take it: support resting on the AI reviewer, support that still waits on
# the expert, unproven, not tested, and a model's own stance label or AI-reviewed tier.
NEVER_SUPPORT = re.compile(r"v-supai|v-await|v-unp|v-nt|b-ai|b-open|ai_reviewed")
# The Supported count and heading stand for a whole group, which can hold a claim whose support
# rests on the AI reviewer. Their green rules must carry one of these guards, so one such claim
# turns the group's marks back to ink: on Claims the page holds no v-supai row; on the case page
# ui/pages.py did not mark the list ai-support.
AGGREGATE = re.compile(r"\.t-sup(?![a-z])|#sup(?![a-z])")
AI_GUARDS = (":not(:has(.verdict.v-supai))", ":not(.ai-support)")
SPACING = {f"--s{i + 1}": f"{px}px" for i, px in enumerate((4, 8, 12, 16, 24, 32, 48, 64))}
TYPE = {
    "--t1": "12px",
    "--l1": "16px",
    "--t2": "14px",
    "--l2": "20px",
    "--t3": "16px",
    "--l3": "24px",
    "--t4": "20px",
    "--l4": "28px",
    "--t5": "28px",
    "--l5": "36px",
}

_SPACE_PROP = re.compile(
    r"^(margin|padding)(-(top|right|bottom|left|inline|block)(-(start|end))?)?$"
    r"|^(gap|row-gap|column-gap|inset|top|right|bottom|left)$"
)
# 0, auto, a percentage, a step of the scale (or its negative), or the sidebar's width, which
# is the one layout offset (the page sits beside the fixed sidebar).
_SPACE_VALUE = re.compile(
    r"^(0|auto|inherit|-?\d+(\.\d+)?%|var\(--s[1-8]\)|calc\(-1 \* var\(--s[1-8]\)\)"
    r"|var\(--sidebar\))$"
)
_FONT = re.compile(
    r"^(inherit|(400|600) var\(--t[1-5]\)/var\(--l[1-5]\) var\(--(sans|mono|wordmark)\))$"
)
_COLOR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color-mix|color)\("
)
_COLOR_PROP = re.compile(r"color|background|border|outline|fill|stroke")
_NAMED = re.compile(
    r"\b(white|black|red|green|blue|gray|grey|silver|yellow|orange|purple|brown|pink|maroon"
    r"|navy|teal|olive|lime|aqua|fuchsia)\b"
)


def _rules(css: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Each rule as (selector, its `property: value` pairs), comments removed. A rule inside an
    @media block is listed like any other; the block itself has no declarations of its own."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out: list[tuple[str, list[tuple[str, str]]]] = []
    for selector, body in re.findall(r"([^{}]*)\{([^{}]*)\}", css):
        block: list[tuple[str, str]] = []
        for decl in body.split(";"):
            if ":" in decl:
                prop, value = decl.split(":", 1)
                block.append((prop.strip(), " ".join(value.split())))
        out.append((" ".join(selector.split()), block))
    return out


def _blocks(css: str) -> list[list[tuple[str, str]]]:
    """Each rule's `property: value` pairs, one list per rule, comments removed."""
    return [block for _, block in _rules(css)]


def _declarations(css: str) -> list[tuple[str, str]]:
    """Every `property: value` pair in the stylesheet."""
    return [decl for block in _blocks(css) for decl in block]


def _parts(value: str) -> list[str]:
    """A value's space-separated parts, keeping each function call whole."""
    out: list[str] = []
    depth = 0
    cur = ""
    for ch in value:
        depth += ch == "("
        depth -= ch == ")"
        if ch == " " and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return [*out, cur] if cur else out


def _tokens() -> dict[str, str]:
    css = re.sub(r"/\*.*?\*/", "", TOKENS_CSS, flags=re.S)
    return dict(re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", css))


def _luminance(color: str) -> float:
    """WCAG relative luminance of a #rrggbb color."""
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    """WCAG contrast ratio of two token names."""
    hi, lo = sorted((_luminance(COLORS[a]), _luminance(COLORS[b])), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _token(value: str) -> str | None:
    """The color token a value is, when it is exactly one."""
    m = re.fullmatch(r"var\((--[a-z-]+)\)", value)
    return m.group(1) if m and m.group(1) in COLORS else None


def _app_css() -> str:
    assert TOKENS_CSS in THEME_CSS
    return (THEME_CSS + PAGE_CSS).replace(TOKENS_CSS, "")


def _app_blocks() -> list[list[tuple[str, str]]]:
    return _blocks(_app_css())


def _app_declarations() -> list[tuple[str, str]]:
    return _declarations(_app_css())


def test_the_token_block_is_the_agreed_scales_and_colors() -> None:
    tokens = _tokens()
    for name, value in {**COLORS, **SPACING, **TYPE}.items():
        assert tokens.get(name) == value, name
    literals = set(re.findall(r"#[0-9a-fA-F]{3,8}\b", TOKENS_CSS))
    assert literals == set(COLORS.values())
    assert not re.search(r"\b(rgba?|hsla?|oklch|color-mix)\(", TOKENS_CSS)
    assert tokens["--radius"] == "4px"


def test_no_color_outside_the_tokens() -> None:
    bad = [
        (prop, value)
        for prop, value in _app_declarations()
        if _COLOR_LITERAL.search(value) or (_COLOR_PROP.search(prop) and _NAMED.search(value))
    ]
    assert bad == []
    # the inline mark takes its two colors from CSS classes, not from fills of its own
    assert not _COLOR_LITERAL.search(MARK)


def test_text_passes_aa_on_every_fill_it_sits_on() -> None:
    """Each text color on the page, on the quiet fill and on its own wash; ink and muted on every
    wash and on the highlighter; and every rule that sets a text color and a fill together."""
    pairs = {(text, "--paper") for text in TEXT_COLORS}
    pairs |= {(text, "--line") for text in TEXT_COLORS}
    pairs |= {(hue, f"{hue}-wash") for hue in ("--accent", "--support", "--signal")}
    pairs |= {
        (text, fill)
        for text in ("--ink", "--muted")
        for fill in ("--accent-wash", "--support-wash", "--signal-wash", "--quote")
    }
    for _, block in _rules(_app_css()):
        rule = dict(block)
        text = _token(rule.get("color", ""))
        fill = _token(rule.get("background", "")) or _token(rule.get("background-color", ""))
        if text and fill:
            pairs.add((text, fill))
    bad = {pair: round(_contrast(*pair), 2) for pair in sorted(pairs) if _contrast(*pair) < AA}
    assert bad == {}


def test_support_green_reaches_only_what_earned_it() -> None:
    """Green says "for the claim as stated, and someone or the code checks stand behind it". A
    model's stance label, the AI reviewer's acceptance, support that waits on the expert,
    unproven and not tested never take it, so an unconfirmed item cannot look confirmed."""
    bad: list[str] = []
    for selector, block in _rules(_app_css()):
        if not any("--support" in value for _, value in block):
            continue
        for one in selector.split(","):
            guarded = any(guard in one for guard in AI_GUARDS)
            for guard in AI_GUARDS:
                one = one.replace(guard, "")
            if not SUPPORT_HOOKS.search(one) or NEVER_SUPPORT.search(one):
                bad.append(one.strip())
            elif AGGREGATE.search(one) and not guarded:
                bad.append(f"unguarded aggregate: {one.strip()}")
    assert bad == []
    # an assumption covered only by the AI reviewer is turned back to muted, after the green rule
    rules = _rules(_app_css())
    green = next(i for i, (s, _) in enumerate(rules) if s.endswith("li.ok .said"))
    ai = next(i for i, (s, _) in enumerate(rules) if "li.ok[data-tier=ai_reviewed] .said" in s)
    assert ai > green and dict(rules[ai][1])["color"] == "var(--muted)"
    # the AI-reviewed Supported mark keeps the base ring: no rule gives v-supai a color at all
    for guard in AI_GUARDS:
        rules = [(s.replace(guard, ""), block) for s, block in rules]
    assert not any("v-supai" in s for s, _ in rules)


def test_no_gradient_shadow_or_opacity_shade() -> None:
    bad = [
        (prop, value)
        for prop, value in _app_declarations()
        if "gradient" in value
        or "shadow" in prop
        or "shadow" in value
        or (prop == "opacity" and value not in ("0", "1"))
    ]
    assert bad == []


def test_spacing_comes_from_the_scale() -> None:
    bad = [
        (prop, value)
        for prop, value in _app_declarations()
        if _SPACE_PROP.match(prop) and not all(_SPACE_VALUE.match(p) for p in _parts(value))
    ]
    assert bad == []


def test_type_comes_from_the_scale() -> None:
    bad: list[tuple[str, str]] = []
    for prop, value in _app_declarations():
        if (
            (prop == "font-size" and not re.fullmatch(r"var\(--t[1-5]\)|inherit", value))
            or (prop == "line-height" and not re.fullmatch(r"var\(--l[1-5]\)|inherit", value))
            or (prop == "font-weight" and value not in ("400", "600", "inherit"))
            or (prop == "font" and not _FONT.match(value))
        ):
            bad.append((prop, value))
    assert bad == []


def test_a_size_keeps_its_own_line_height() -> None:
    """The scale is five size and line-height pairs: a rule that sets both takes one step."""
    bad: list[tuple[str, str]] = []
    for block in _app_blocks():
        rule = dict(block)
        size = re.fullmatch(r"var\(--t([1-5])\)", rule.get("font-size", ""))
        line = re.fullmatch(r"var\(--l([1-5])\)", rule.get("line-height", ""))
        if size and line and size.group(1) != line.group(1):
            bad.append((rule["font-size"], rule["line-height"]))
        short = re.search(r"var\(--t([1-5])\)/var\(--l([1-5])\)", rule.get("font", ""))
        if short and short.group(1) != short.group(2):
            bad.append(("font", rule["font"]))
    assert bad == []


def test_one_radius() -> None:
    bad = [
        (prop, value)
        for prop, value in _app_declarations()
        if prop.endswith("radius")
        and not all(p in ("0", "var(--radius)", "50%") for p in _parts(value))
    ]
    assert bad == []


def test_page_markup_carries_no_inline_styles() -> None:
    """A style attribute would step around the tokens, so nothing under ui/ writes one.

    Two things stay outside this check, and both are outside the app's stylesheet too:
    ui/server.py's bare "unexpected error" page, which is served without any stylesheet, and
    the report's own fragments under core/report/ (the Gaps bars carry each bar's height as a
    style attribute, a value from the data and not a design choice)."""
    for path in sorted((ROOT / "ui").rglob("*.py")):
        if path.name == "server.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "style=" not in text, path.relative_to(ROOT).as_posix()
