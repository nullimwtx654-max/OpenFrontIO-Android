import os, re, json

root = os.path.dirname(os.path.abspath(__file__))
dist = os.environ.get("OPENFRONT_DIST", os.path.join(root, "dist"))
os.makedirs(dist, exist_ok=True)

# 1. Patch Main.ts safely
main_path = os.path.join(root, "src/client/Main.ts")
main_txt = open(main_path).read()
main_txt = main_txt.replace("this.updateJoinUrlForShare(lobby.gameID);", "// no URL rewrite on Android")
old_push = """      const lobbyIdHidden = !this.userSettings.lobbyIdVisibility();
      if (isReplayShellHost(window.location.hostname)) {
        // Keep the canonical replay URL (replay.<domain>/<gameId>): the
        // /game/<id> shape and the #refresh trampoline only exist on the
        // game-server origin, so rewriting here would leave a URL that 404s
        // when reloaded or shared (see VersionedReplay.ts).
        history.pushState(null, "", window.location.pathname);
      } else {
        // Ensure there's a homepage entry in history before adding the lobby entry
        if (window.location.hash === "" || window.location.hash === "#") {
          history.replaceState(null, "", window.location.origin + "#refresh");
        }
        history.pushState(
          null,
          "",
          currentPagePath(
            lobbyIdHidden
              ? "/streamer-mode"
              : `${ClientEnv.gamePath(lobby.gameID)}?live`,
          ),
        );
      }"""
if old_push in main_txt:
    main_txt = main_txt.replace(old_push, '      try { history.pushState(null, "", "#in-game"); } catch {}')
open(main_path, "w").write(main_txt)

# 2. Generate comprehensive Tailwind v4 + Custom CSS
PALETTE = {
  "white": "#ffffff",
  "black": "#000000",
  "transparent": "transparent",
  "malibu-blue": "#0084d1",
  "aquarius": "#3fa9f5",
  "dawn-blue": "#cccccc",
  "bright-white": "#ffffff",
  "bright-blue": "#1e90ff",
  "cyber-yellow": "#ffd700",
  "limestone": "#999999",
  "deep-navy": "#0a1628",
  "hex-cyan": "#00c8ff",
  "frame-orange": "#f97316",
  "surface": "#0a1628",
  "slate-50": "#f8fafc", "slate-100": "#f1f5f9", "slate-200": "#e2e8f0", "slate-300": "#cbd5e1", "slate-400": "#94a3b8", "slate-500": "#64748b", "slate-600": "#475569", "slate-700": "#334155", "slate-800": "#1e293b", "slate-900": "#0f172a", "slate-950": "#020617",
  "gray-50": "#f9fafb", "gray-100": "#f3f4f6", "gray-200": "#e5e7eb", "gray-300": "#d1d5db", "gray-400": "#9ca3af", "gray-500": "#6b7280", "gray-600": "#4b5563", "gray-700": "#374151", "gray-800": "#1f2937", "gray-900": "#111827", "gray-950": "#030712",
  "zinc-50": "#fafafa", "zinc-100": "#f4f4f5", "zinc-200": "#e4e4e7", "zinc-300": "#d4d4d8", "zinc-400": "#a1a1aa", "zinc-500": "#71717a", "zinc-600": "#52525b", "zinc-700": "#3f3f46", "zinc-800": "#27272a", "zinc-900": "#18181b", "zinc-950": "#09090b",
  "neutral-50": "#fafafa", "neutral-100": "#f5f5f5", "neutral-200": "#e5e5e5", "neutral-300": "#d4d4d4", "neutral-400": "#a3a3a3", "neutral-500": "#737373", "neutral-600": "#525252", "neutral-700": "#404040", "neutral-800": "#262626", "neutral-900": "#171717", "neutral-950": "#0a0a0a",
  "red-100": "#fee2e2", "red-200": "#fecaca", "red-300": "#fca5a5", "red-400": "#f87171", "red-500": "#ef4444", "red-600": "#dc2626", "red-700": "#b91c1c", "red-800": "#991b1b", "red-900": "#7f1d1d",
  "orange-300": "#fdba74", "orange-400": "#fb923c", "orange-500": "#f97316", "orange-600": "#ea580c",
  "amber-200": "#fde68a", "amber-300": "#fcd34d", "amber-400": "#fbbf24", "amber-500": "#f59e0b", "amber-600": "#d97706",
  "yellow-100": "#fef9c3", "yellow-200": "#fef08a", "yellow-300": "#fde047", "yellow-400": "#facc15", "yellow-500": "#eab308", "yellow-600": "#ca8a04",
  "green-200": "#bbf7d0", "green-300": "#86efac", "green-400": "#4ade80", "green-500": "#22c55e", "green-600": "#16a34a", "green-700": "#15803d", "green-800": "#166534",
  "emerald-300": "#6ee7b7", "emerald-400": "#34d399", "emerald-500": "#10b981", "emerald-600": "#059669", "emerald-700": "#047857",
  "teal-400": "#2dd4bf", "teal-500": "#14b8a6",
  "cyan-300": "#67e8f9", "cyan-400": "#22d3ee", "cyan-500": "#06b6d4",
  "sky-300": "#7dd3fc", "sky-400": "#38bdf8", "sky-500": "#0ea5e9", "sky-600": "#0284c7",
  "blue-100": "#dbeafe", "blue-200": "#bfdbfe", "blue-300": "#93c5fd", "blue-400": "#60a5fa", "blue-500": "#3b82f6", "blue-600": "#2563eb", "blue-700": "#1d4ed8", "blue-800": "#1e40af", "blue-900": "#1e3a8a",
  "indigo-400": "#818cf8", "indigo-500": "#6366f1", "indigo-600": "#4f46e5",
  "purple-300": "#d8b4fe", "purple-400": "#c084fc", "purple-500": "#a855f7", "purple-600": "#9333ea",
  "pink-400": "#f472b6", "pink-500": "#ec4899",
}

def hex_to_rgba(hex_str, alpha):
    if not hex_str.startswith("#"):
        return hex_str
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"

def resolve_color(c_spec):
    if "/" in c_spec:
        base, op = c_spec.split("/", 1)
        try:
            if op.startswith("[") and op.endswith("]"):
                alpha = float(op[1:-1])
            else:
                alpha = float(op) / 100.0
        except:
            return None
        if base in PALETTE:
            return hex_to_rgba(PALETTE[base], alpha)
        if base.startswith("[") and base.endswith("]"):
            return base[1:-1]
    if c_spec in PALETTE:
        return PALETTE[c_spec]
    if c_spec.startswith("[") and c_spec.endswith("]"):
        return c_spec[1:-1].replace("_", " ")
    return None

def spacing(val):
    if val == "px": return "1px"
    if val == "auto": return "auto"
    if val == "full": return "100%"
    if val.startswith("[") and val.endswith("]"):
        return val[1:-1].replace("_", " ")
    try:
        return f"{float(val) * 0.25}rem"
    except:
        return None

# Collect all class tokens from index.html and src/client/**/*.ts
tokens = set()
for dirpath, _, filenames in os.walk(os.path.join(root, "src/client")):
    for fn in filenames:
        if fn.endswith(".ts"):
            txt = open(os.path.join(dirpath, fn), errors="ignore").read()
            for m in re.findall(r'["\x27`]([a-zA-Z0-9_:/\-\[\].%!&\s]+)["\x27`]', txt):
                for tok in re.split(r'\s+', m):
                    if tok and len(tok) < 80:
                        tokens.add(tok)
            for tok in re.findall(r'[a-zA-Z0-9_:/\-\[\].%!&]+', txt):
                if any(tok.startswith(p) for p in (
                    'bg-', 'text-', 'border-', 'p-', 'px-', 'py-', 'pt-', 'pb-', 'pl-', 'pr-',
                    'm-', 'mx-', 'my-', 'mt-', 'mb-', 'ml-', 'mr-', 'w-', 'h-', 'min-', 'max-',
                    'flex', 'grid', 'items-', 'justify-', 'gap-', 'rounded', 'shadow', 'opacity-',
                    'z-', 'top-', 'bottom-', 'left-', 'right-', 'inset-', 'overflow-', 'visible',
                    'invisible', 'hidden', 'block', 'inline', 'relative', 'absolute', 'fixed',
                    'sticky', 'pointer-events-', 'cursor-', 'select-', 'font-', 'tracking-',
                    'leading-', 'uppercase', 'lowercase', 'capitalize', 'truncate', 'whitespace-',
                    'transition', 'duration-', 'scale-', 'rotate-', 'translate-', '-translate-',
                    'backdrop-', 'sm:', 'md:', 'lg:', 'xl:', '2xl:', 'hover:', 'active:', 'focus:',
                    'disabled:', 'in-[', '[.in-game', '[&'
                )):
                    tokens.add(tok)

html_txt = open(os.path.join(root, "index.html")).read()
for m in re.findall(r'class\s*=\s*"([^"]+)"', html_txt):
    for tok in re.split(r'\s+', m):
        if tok: tokens.add(tok)

def escape_cls(cls):
    return re.sub(r'([^a-zA-Z0-9_-])', r'\\\1', cls)

def base_rule(tok):
    important = False
    if tok.startswith("!"):
        important = True
        tok = tok[1:]
    if tok.endswith("!"):
        important = True
        tok = tok[:-1]
    imp = " !important" if important else ""

    # Exact static map
    STATIC = {
        "block": "display: block",
        "inline-block": "display: inline-block",
        "inline": "display: inline",
        "flex": "display: flex",
        "inline-flex": "display: inline-flex",
        "grid": "display: grid",
        "inline-grid": "display: inline-grid",
        "contents": "display: contents",
        "hidden": "display: none",
        "visible": "visibility: visible",
        "invisible": "visibility: hidden; pointer-events: none",
        "overflow-x-clip": "overflow-x: clip",
        "overflow-y-clip": "overflow-y: clip",
        "tabular-nums": "font-variant-numeric: tabular-nums",
        "no-underline": "text-decoration: none",
        "underline": "text-decoration: underline",
        "table": "display: table",
        "flex-row": "flex-direction: row",
        "flex-col": "flex-direction: column",
        "flex-wrap": "flex-wrap: wrap",
        "flex-nowrap": "flex-wrap: nowrap",
        "flex-1": "flex: 1 1 0%",
        "flex-auto": "flex: 1 1 auto",
        "flex-initial": "flex: 0 1 auto",
        "flex-none": "flex: none",
        "shrink-0": "flex-shrink: 0",
        "shrink": "flex-shrink: 1",
        "grow": "flex-grow: 1",
        "grow-0": "flex-grow: 0",
        "basis-full": "flex-basis: 100%",
        "items-start": "align-items: flex-start",
        "items-end": "align-items: flex-end",
        "items-center": "align-items: center",
        "items-baseline": "align-items: baseline",
        "items-stretch": "align-items: stretch",
        "justify-start": "justify-content: flex-start",
        "justify-end": "justify-content: flex-end",
        "justify-center": "justify-content: center",
        "justify-between": "justify-content: space-between",
        "justify-around": "justify-content: space-around",
        "justify-evenly": "justify-content: space-evenly",
        "content-start": "align-content: flex-start",
        "content-center": "align-content: center",
        "self-auto": "align-self: auto",
        "self-start": "align-self: flex-start",
        "self-end": "align-self: flex-end",
        "self-center": "align-self: center",
        "self-stretch": "align-self: stretch",
        "justify-self-start": "justify-self: start",
        "justify-self-end": "justify-self: end",
        "justify-self-center": "justify-self: center",
        "relative": "position: relative",
        "absolute": "position: absolute",
        "fixed": "position: fixed",
        "sticky": "position: sticky",
        "static": "position: static",
        "inset-0": "top: 0; right: 0; bottom: 0; left: 0",
        "inset-x-0": "left: 0; right: 0",
        "inset-y-0": "top: 0; bottom: 0",
        "w-full": "width: 100%",
        "w-screen": "width: 100vw",
        "w-fit": "width: fit-content",
        "w-auto": "width: auto",
        "w-px": "width: 1px",
        "min-w-0": "min-width: 0px",
        "min-w-full": "min-width: 100%",
        "max-w-none": "max-width: none",
        "max-w-xs": "max-width: 20rem",
        "max-w-sm": "max-width: 24rem",
        "max-w-md": "max-width: 28rem",
        "max-w-lg": "max-width: 32rem",
        "max-w-xl": "max-width: 36rem",
        "max-w-2xl": "max-width: 42rem",
        "max-w-3xl": "max-width: 48rem",
        "max-w-4xl": "max-width: 56rem",
        "max-w-5xl": "max-width: 64rem",
        "max-w-6xl": "max-width: 72rem",
        "max-w-7xl": "max-width: 80rem",
        "max-w-full": "max-width: 100%",
        "h-full": "height: 100%",
        "h-screen": "height: 100vh",
        "h-dvh": "height: 100dvh",
        "h-fit": "height: fit-content",
        "h-auto": "height: auto",
        "h-px": "height: 1px",
        "min-h-0": "min-height: 0px",
        "min-h-full": "min-height: 100%",
        "min-h-screen": "min-height: 100vh",
        "min-h-dvh": "min-height: 100dvh",
        "max-h-full": "max-height: 100%",
        "max-h-screen": "max-height: 100vh",
        "overflow-auto": "overflow: auto",
        "overflow-hidden": "overflow: hidden",
        "overflow-visible": "overflow: visible",
        "overflow-scroll": "overflow: scroll",
        "overflow-x-auto": "overflow-x: auto",
        "overflow-y-auto": "overflow-y: auto",
        "overflow-x-hidden": "overflow-x: hidden",
        "overflow-y-hidden": "overflow-y: hidden",
        "truncate": "overflow: hidden; text-overflow: ellipsis; white-space: nowrap",
        "whitespace-nowrap": "white-space: nowrap",
        "whitespace-pre-wrap": "white-space: pre-wrap",
        "break-words": "overflow-wrap: break-word",
        "break-all": "word-break: break-all",
        "rounded-none": "border-radius: 0px",
        "rounded-xs": "border-radius: 0.125rem",
        "rounded-sm": "border-radius: 0.25rem",
        "rounded": "border-radius: 0.25rem",
        "rounded-md": "border-radius: 0.375rem",
        "rounded-lg": "border-radius: 0.5rem",
        "rounded-xl": "border-radius: 0.75rem",
        "rounded-2xl": "border-radius: 1rem",
        "rounded-3xl": "border-radius: 1.5rem",
        "rounded-full": "border-radius: 9999px",
        "rounded-t-lg": "border-top-left-radius: 0.5rem; border-top-right-radius: 0.5rem",
        "rounded-tr-lg": "border-top-right-radius: 0.5rem",
        "rounded-bl-lg": "border-bottom-left-radius: 0.5rem",
        "border": "border-width: 1px; border-style: solid",
        "border-0": "border-width: 0px",
        "border-2": "border-width: 2px; border-style: solid",
        "border-4": "border-width: 4px; border-style: solid",
        "border-t": "border-top-width: 1px; border-top-style: solid",
        "border-b": "border-bottom-width: 1px; border-bottom-style: solid",
        "border-l": "border-left-width: 1px; border-left-style: solid",
        "border-r": "border-right-width: 1px; border-right-style: solid",
        "border-y": "border-top-width: 1px; border-bottom-width: 1px; border-style: solid",
        "border-x": "border-left-width: 1px; border-right-width: 1px; border-style: solid",
        "border-none": "border-style: none",
        "text-xs": "font-size: 0.75rem; line-height: 1rem",
        "text-sm": "font-size: 0.875rem; line-height: 1.25rem",
        "text-base": "font-size: 1rem; line-height: 1.5rem",
        "text-lg": "font-size: 1.125rem; line-height: 1.75rem",
        "text-xl": "font-size: 1.25rem; line-height: 1.75rem",
        "text-2xl": "font-size: 1.5rem; line-height: 2rem",
        "text-3xl": "font-size: 1.875rem; line-height: 2.25rem",
        "text-4xl": "font-size: 2.25rem; line-height: 2.5rem",
        "font-normal": "font-weight: 400",
        "font-medium": "font-weight: 500",
        "font-semibold": "font-weight: 600",
        "font-bold": "font-weight: 700",
        "font-extrabold": "font-weight: 800",
        "font-black": "font-weight: 900",
        "font-sans": "font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "font-mono": "font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        "italic": "font-style: italic",
        "not-italic": "font-style: normal",
        "uppercase": "text-transform: uppercase",
        "lowercase": "text-transform: lowercase",
        "capitalize": "text-transform: capitalize",
        "leading-none": "line-height: 1",
        "leading-tight": "line-height: 1.25",
        "leading-snug": "line-height: 1.375",
        "leading-normal": "line-height: 1.5",
        "leading-relaxed": "line-height: 1.625",
        "tracking-tight": "letter-spacing: -0.025em",
        "tracking-normal": "letter-spacing: 0em",
        "tracking-wide": "letter-spacing: 0.025em",
        "tracking-wider": "letter-spacing: 0.05em",
        "tracking-widest": "letter-spacing: 0.1em",
        "text-left": "text-align: left",
        "text-center": "text-align: center",
        "text-right": "text-align: right",
        "align-middle": "vertical-align: middle",
        "select-none": "user-select: none",
        "select-text": "user-select: text",
        "select-all": "user-select: all",
        "pointer-events-none": "pointer-events: none",
        "pointer-events-auto": "pointer-events: auto",
        "cursor-pointer": "cursor: pointer",
        "cursor-default": "cursor: default",
        "cursor-not-allowed": "cursor: not-allowed",
        "shadow-xs": "box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05)",
        "shadow-sm": "box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1)",
        "shadow": "box-shadow: 0 1px 3px 0 rgba(0,0,0,0.2), 0 1px 2px -1px rgba(0,0,0,0.2)",
        "shadow-md": "box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3), 0 2px 4px -2px rgba(0,0,0,0.3)",
        "shadow-lg": "box-shadow: 0 10px 15px -3px rgba(0,0,0,0.4), 0 4px 6px -4px rgba(0,0,0,0.4)",
        "shadow-xl": "box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5), 0 8px 10px -6px rgba(0,0,0,0.5)",
        "shadow-2xl": "box-shadow: 0 25px 50px -12px rgba(0,0,0,0.6)",
        "outline-none": "outline: 2px solid transparent; outline-offset: 2px",
        "backdrop-blur-xs": "backdrop-filter: blur(2px)",
        "backdrop-blur-sm": "backdrop-filter: blur(4px)",
        "backdrop-blur": "backdrop-filter: blur(8px)",
        "backdrop-blur-md": "backdrop-filter: blur(12px)",
        "backdrop-blur-lg": "backdrop-filter: blur(16px)",
        "backdrop-blur-xl": "backdrop-filter: blur(24px)",
        "transition": "transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1)",
        "transition-all": "transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1)",
        "transition-colors": "transition: color, background-color, border-color, text-decoration-color, fill, stroke 150ms cubic-bezier(0.4, 0, 0.2, 1)",
        "transition-opacity": "transition: opacity 150ms cubic-bezier(0.4, 0, 0.2, 1)",
        "transition-transform": "transition: transform 150ms cubic-bezier(0.4, 0, 0.2, 1)",
        "duration-150": "transition-duration: 150ms",
        "duration-200": "transition-duration: 200ms",
        "duration-300": "transition-duration: 300ms",
        "duration-500": "transition-duration: 500ms",
        "ease-in-out": "transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1)",
        "ease-out": "transition-timing-function: cubic-bezier(0, 0, 0.2, 1)",
        "animate-spin": "animation: spin 1s linear infinite",
        "animate-ping": "animation: ping 1s cubic-bezier(0, 0, 0.2, 1) infinite",
        "animate-pulse": "animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "object-contain": "object-fit: contain",
        "object-cover": "object-fit: cover",
        "bg-cover": "background-size: cover",
        "bg-contain": "background-size: contain",
        "bg-center": "background-position: center",
        "bg-no-repeat": "background-repeat: no-repeat",
        "-translate-x-full": "transform: translateX(-100%)",
        "translate-x-0": "transform: translateX(0)",
        "translate-x-full": "transform: translateX(100%)",
        "-translate-x-1/2": "transform: translateX(-50%)",
        "-translate-y-1/2": "transform: translateY(-50%)",
        "rotate-90": "transform: rotate(90deg)",
        " rotate-180": "transform: rotate(180deg)",
    }
    if tok in STATIC:
        return STATIC[tok] + imp

    # Spacing: p, px, py, pt, pb, pl, pr, m, mx, my, mt, mb, ml, mr, gap, gap-x, gap-y
    m = re.match(r'^(-?)(p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|gap|gap-x|gap-y)-(.+)$', tok)
    if m:
        neg, kind, rest = m.groups()
        sp = spacing(rest)
        if sp:
            if neg == "-" and not sp.startswith("-"): sp = "-" + sp
            MAP = {
                "p": ["padding"], "px": ["padding-left", "padding-right"], "py": ["padding-top", "padding-bottom"],
                "pt": ["padding-top"], "pb": ["padding-bottom"], "pl": ["padding-left"], "pr": ["padding-right"],
                "m": ["margin"], "mx": ["margin-left", "margin-right"], "my": ["margin-top", "margin-bottom"],
                "mt": ["margin-top"], "mb": ["margin-bottom"], "ml": ["margin-left"], "mr": ["margin-right"],
                "gap": ["gap"], "gap-x": ["column-gap"], "gap-y": ["row-gap"],
            }
            return "; ".join(f"{prop}: {sp}{imp}" for prop in MAP[kind])

    # Positioning: top, bottom, left, right
    m = re.match(r'^(-?)(top|bottom|left|right)-(.+)$', tok)
    if m:
        neg, prop, rest = m.groups()
        if rest == "1/2": val = "50%"
        else: val = spacing(rest)
        if val:
            if neg == "-": val = "-" + val
            return f"{prop}: {val}{imp}"

    # Width / Height / Size: w-*, h-*, size-*, min-w-*, max-w-*, min-h-*, max-h-*
    m = re.match(r'^(w|h|size|min-w|max-w|min-h|max-h)-(.+)$', tok)
    if m:
        kind, rest = m.groups()
        if rest == "1/2": val = "50%"
        elif rest == "1/3": val = "33.333333%"
        elif rest == "2/3": val = "66.666667%"
        elif rest == "1/4": val = "25%"
        elif rest == "3/4": val = "75%"
        else: val = spacing(rest)
        if val:
            if kind == "w": return f"width: {val}{imp}"
            if kind == "h": return f"height: {val}{imp}"
            if kind == "size": return f"width: {val}{imp}; height: {val}{imp}"
            if kind == "min-w": return f"min-width: {val}{imp}"
            if kind == "max-w": return f"max-width: {val}{imp}"
            if kind == "min-h": return f"min-height: {val}{imp}"
            if kind == "max-h": return f"max-height: {val}{imp}"

    # Colors: bg-*, text-*, border-*
    m = re.match(r'^(bg|text|border)-(.+)$', tok)
    if m:
        kind, rest = m.groups()
        col = resolve_color(rest)
        if col:
            if kind == "bg": return f"background-color: {col}{imp}"
            if kind == "text": return f"color: {col}{imp}"
            if kind == "border": return f"border-color: {col}{imp}"

    # Font size arbitrary: text-[...]
    m = re.match(r'^text-\[(.+)\]$', tok)
    if m:
        return f"font-size: {m.group(1).replace('_', ' ')}{imp}"

    # Opacity: opacity-*
    m = re.match(r'^opacity-(\d+)$', tok)
    if m:
        return f"opacity: {int(m.group(1)) / 100.0}{imp}"

    # Z-index: z-*
    m = re.match(r'^(-?)z-(.+)$', tok)
    if m:
        neg, rest = m.groups()
        val = rest[1:-1] if (rest.startswith("[") and rest.endswith("]")) else rest
        if val.isdigit():
            return f"z-index: {'-' if neg else ''}{val}{imp}"

    # Grid columns / rows / spans
    m = re.match(r'^grid-cols-(\d+)$', tok)
    if m: return f"grid-template-columns: repeat({m.group(1)}, minmax(0, 1fr)){imp}"
    m = re.match(r'^grid-cols-\[(.+)\]$', tok)
    if m: return f"grid-template-columns: {m.group(1).replace('_', ' ')}{imp}"
    m = re.match(r'^col-span-(\d+)$', tok)
    if m: return f"grid-column: span {m.group(1)} / span {m.group(1)}{imp}"
    m = re.match(r'^col-start-(\d+)$', tok)
    if m: return f"grid-column-start: {m.group(1)}{imp}"
    m = re.match(r'^row-start-(\d+)$', tok)
    if m: return f"grid-row-start: {m.group(1)}{imp}"
    m = re.match(r'^order-(\d+|none)$', tok)
    if m:
        v = "0" if m.group(1) == "none" else m.group(1)
        return f"order: {v}{imp}"

    # Aspect ratio
    m = re.match(r'^aspect-\[(.+)\]$', tok)
    if m: return f"aspect-ratio: {m.group(1)}{imp}"
    if tok == "aspect-square": return f"aspect-ratio: 1 / 1{imp}"
    if tok == "aspect-video": return f"aspect-ratio: 16 / 9{imp}"

    # Flex arbitrary
    m = re.match(r'^flex-\[(.+)\]$', tok)
    if m: return f"flex: {m.group(1)}{imp}"

    # Space-y / Space-x
    m = re.match(r'^space-(x|y)-(.+)$', tok)
    if m:
        axis, rest = m.groups()
        sp = spacing(rest)
        if sp:
            prop = "margin-left" if axis == "x" else "margin-top"
            return ("SPACE_CHILD", f"{prop}: {sp}{imp}")

    return None

css_rules = []
media_rules = {"sm": [], "md": [], "lg": [], "xl": [], "2xl": []}
BP = {"sm": "640px", "md": "768px", "lg": "1024px", "xl": "1280px", "2xl": "1536px"}

for full_tok in sorted(tokens):
    parts = full_tok.split(":")
    base = parts[-1]
    mods = parts[:-1]
    decl = base_rule(base)
    if not decl:
        continue
    sel = f".{escape_cls(full_tok)}"
    if isinstance(decl, tuple) and decl[0] == "SPACE_CHILD":
        sel = f"{sel} > :not([hidden]) ~ :not([hidden])"
        decl = decl[1]

    bp = None
    for mod in mods:
        if mod in BP:
            bp = mod
        elif mod == "hover":
            sel = f"{sel}:hover"
        elif mod == "active":
            sel = f"{sel}:active"
        elif mod == "focus":
            sel = f"{sel}:focus"
        elif mod == "disabled":
            sel = f"{sel}:disabled"
        elif mod == "in-[.in-game]":
            sel = f".in-game {sel}"
        elif mod == "[.in-game_&]":
            sel = f".in-game {sel}"
        elif mod == "in-[.page-open]":
            sel = f".page-open {sel}"
        elif mod == "[&.open]":
            sel = f"{sel}.open"
        elif mod == "[&.active]":
            sel = f"{sel}.active"
        elif mod == "[&:empty]":
            sel = f"{sel}:empty"

    rule_str = f"{sel} {{ {decl}; }}"
    if bp:
        media_rules[bp].append(rule_str)
    else:
        css_rules.append(rule_str)

# Build complete CSS
css_out = ["""
:root {
  --default-ring-width: 3px;
  --default-ring-color: #0084d1;
  --font-display: "OpenFront", Inter, Arial, sans-serif;
  --color-malibu-blue: #0084d1;
  --color-aquarius: #3fa9f5;
  --color-dawn-blue: #cccccc;
  --color-bright-white: #ffffff;
  --color-bright-blue: #1e90ff;
  --color-cyber-yellow: #ffd700;
  --color-limestone: #999999;
  --color-deep-navy: #0a1628;
  --color-hex-cyan: #00c8ff;
  --color-frame-orange: #f97316;
  --color-surface: #0a1628;
  --color-gray-200: #e5e7eb;
  --color-gray-400: #9ca3af;
  --color-gray-700: #374151;
  --color-gray-800: #1f2937;
}
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes ping { 75%, 100% { transform: scale(2); opacity: 0; } }
@keyframes pulse { 50% { opacity: .5; } }
*, ::after, ::before { box-sizing: border-box; border-width: 0; border-style: solid; border-color: rgba(255,255,255,0.15); }
html, body { margin: 0; padding: 0; width: 100%; height: 100%; background-color: #111827; color: #ffffff; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; -webkit-tap-highlight-color: transparent; }
button { background: transparent; color: inherit; font: inherit; cursor: pointer; }
"""]

# Add custom CSS files from src/client/styles/
for rel in [
    "src/client/styles/core/variables.css",
    "src/client/styles/core/typography.css",
    "src/client/styles/core/flag-animation.css",
    "src/client/styles/components/controls.css",
    "src/client/styles/components/setting.css",
    "src/client/styles/layout/container.css",
    "src/client/styles/layout/header.css",
    "src/client/halloween.css",
]:
    p = os.path.join(root, rel)
    if os.path.exists(p):
        css_out.append(open(p).read())

# Add non-@theme/@import parts of src/client/styles.css
raw_styles = open(os.path.join(root, "src/client/styles.css")).read()
raw_styles = re.sub(r'@import\s+[^;]+;', '', raw_styles)
raw_styles = re.sub(r'@custom-variant\s+[^;]+;', '', raw_styles)
raw_styles = re.sub(r'@theme\s*\{[\s\S]*?\n\}', '', raw_styles)
raw_styles = raw_styles.replace("@layer base {", "").rstrip()
if raw_styles.endswith("}"): pass
css_out.append(raw_styles)

css_out.extend(css_rules)
for bp, rules in media_rules.items():
    if rules:
        css_out.append(f"@media (min-width: {BP[bp]}) {{\n  " + "\n  ".join(rules) + "\n}")

css_out.append('\nhtml, body {\n  margin: 0 !important;\n  padding: 0 !important;\n  width: 100%;\n  height: 100%;\n  background-color: #090d16;\n}\nbody:not(.in-game) #bottom-hud-container,\nbody:not(.in-game) #right-hud-container,\nbody:not(.in-game) emoji-table,\nbody:not(.in-game) build-menu,\nbody:not(.in-game) win-modal,\nbody:not(.in-game) new-lobby-prompt,\nbody:not(.in-game) game-right-sidebar,\nbody:not(.in-game) replay-panel,\nbody:not(.in-game) settings-modal,\nbody:not(.in-game) #game-settings,\nbody:not(.in-game) player-panel,\nbody:not(.in-game) spawn-timer,\nbody:not(.in-game) immunity-timer,\nbody:not(.in-game) in-game-promo,\nbody:not(.in-game) alert-frame,\nbody:not(.in-game) chat-modal,\nbody:not(.in-game) multi-tab-modal,\nbody:not(.in-game) game-left-sidebar,\nbody:not(.in-game) performance-overlay,\nbody:not(.in-game) player-info-overlay,\nbody:not(.in-game) heads-up-message {\n  display: none !important;\n  pointer-events: none !important;\n}\n')
final_css = "\n".join(css_out)
final_css += '\n.origin-left { transform-origin: left !important; }\n.origin-right { transform-origin: right !important; }\n.origin-center { transform-origin: center !important; }\n.grid-rows-1 { grid-template-rows: repeat(1, minmax(0, 1fr)) !important; }\n.grid-flow-col { grid-auto-flow: column !important; }\n.z-900 { z-index: 900 !important; }\n.z-1000 { z-index: 1000 !important; }\n.z-2000 { z-index: 2000 !important; }\n.z-10001 { z-index: 10001 !important; }\n.z-10002 { z-index: 10002 !important; }\n.z-10003 { z-index: 10003 !important; }\n.z-10004 { z-index: 10004 !important; }\n#game-input-overlay { z-index: 1 !important; }\n#app, #app canvas { z-index: 0 !important; }\n#bottom-hud-container { z-index: 500 !important; }\n#right-hud-container { z-index: 1000 !important; }\ngame-left-sidebar aside { z-index: 900 !important; }\nsettings-modal .modal-overlay { z-index: 2000 !important; }\n'
final_css += '\nreplay-panel, replay-panel > div, replay-panel button { pointer-events: auto !important; }\ndoomsday-clock-panel, overtime-panel { pointer-events: auto !important; }\n#error-modal, #error-modal pre { color: #111827 !important; white-space: pre-wrap !important; word-break: break-word !important; z-index: 10005 !important; }\n'
open(os.path.join(dist, "styles.css"), "w").write(final_css)
print("Generated dist/styles.css:", len(final_css), "bytes,", len(css_rules), "base utility rules.")
