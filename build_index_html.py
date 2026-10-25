import os, json

root = os.path.dirname(os.path.abspath(__file__))
dist = os.environ.get("OPENFRONT_DIST", os.path.join(root, "dist"))

os.makedirs(dist, exist_ok=True)
# Symlink resource subdirectories into dist/ when present
res_dir = os.path.join(root, "resources")
if os.path.isdir(res_dir):
    for entry in os.listdir(res_dir):
        src_p = os.path.join(res_dir, entry)
        dst_p = os.path.join(dist, entry)
        if not os.path.lexists(dst_p):
            try:
                os.symlink(src_p, dst_p)
            except OSError:
                pass

# Also write worker-inline.js that sets window.__OPENFRONT_WORKER_CODE__
worker_code = open(os.path.join(dist, "worker.js"), "r", encoding="utf-8").read()
with open(os.path.join(dist, "worker-inline.js"), "w", encoding="utf-8") as f:
    f.write(f"window.__OPENFRONT_WORKER_CODE__ = {json.dumps(worker_code)};\n")

styles_css = open(os.path.join(dist, "styles.css"), "r", encoding="utf-8").read()

index_html = f"""<!doctype html>
<html lang="en" class="h-full" translate="no">
  <head>
    <meta charset="UTF-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover"
    />
    <title>OpenFront Android</title>
    <style id="main-styles">
{styles_css}
    </style>
    <script>
      window.BOOTSTRAP_CONFIG = {{
        gitCommit: "android-1.0",
        assetManifest: {{}},
        cdnBase: "",
        gameEnv: "prod",
        turnstileSiteKey: "",
        jwtAudience: "openfront"
      }};
      document.documentElement.style.setProperty(
        "--background-image-url",
        'url("./images/GameplayScreenshot.png")'
      );
      document.documentElement.style.setProperty(
        "--mobile-logo-image-url",
        'url("./images/OpenFrontLogo.svg")'
      );

      // Android file:/// fetch polyfill via XMLHttpRequest
      (function() {{
        const origFetch = window.fetch ? window.fetch.bind(window) : null;
        function xhrFetch(url) {{
          return new Promise((resolve, reject) => {{
            try {{
              const xhr = new XMLHttpRequest();
              xhr.open("GET", url, true);
              xhr.responseType = "arraybuffer";
              xhr.onload = function() {{
                if (xhr.status === 200 || (xhr.status === 0 && xhr.response)) {{
                  const buf = xhr.response;
                  const headers = new Headers();
                  if (url.endsWith(".json")) headers.set("content-type", "application/json");
                  else if (url.endsWith(".svg")) headers.set("content-type", "image/svg+xml");
                  else if (url.endsWith(".webp")) headers.set("content-type", "image/webp");
                  else if (url.endsWith(".png")) headers.set("content-type", "image/png");
                  resolve(new Response(buf, {{ status: 200, statusText: "OK", headers }}));
                }} else {{
                  reject(new Error("XHR status " + xhr.status + " for " + url));
                }}
              }};
              xhr.onerror = function() {{
                reject(new Error("XHR network error for " + url));
              }};
              xhr.send();
            }} catch (e) {{
              reject(e);
            }}
          }});
        }}

        window.fetch = function(input, init) {{
          const url = typeof input === "string" ? input : (input && input.url ? input.url : String(input));
          if (window.location.protocol === "file:" && (!init || !init.method || init.method === "GET")) {{
            return xhrFetch(url);
          }}
          if (origFetch) {{
            return origFetch(input, init).catch((err) => {{
              if (!init || !init.method || init.method === "GET") {{
                return xhrFetch(url);
              }}
              throw err;
            }});
          }}
          return xhrFetch(url);
        }};
      }})();

      // Android hardware back button bridge
      window.__handleAndroidBack = function() {{
        try {{
          const settingsModal = document.querySelector("settings-modal");
          if (settingsModal && settingsModal.open) {{
            settingsModal.closeModal();
            return true;
          }}
          if (document.body.classList.contains("in-game")) {{
            if (settingsModal && typeof settingsModal.openModal === "function") {{
              settingsModal.openModal();
              return true;
            }}
          }}
          if (window.currentPageId && window.currentPageId !== "page-play" && window.showPage) {{
            window.showPage("page-play");
            return true;
          }}
        }} catch (e) {{
          console.warn("Back handler error:", e);
        }}
        return false;
      }};
    </script>
  </head>

  <body
    class="select-none font-sans min-h-screen bg-neutral-800 flex flex-row flex-wrap content-start"
  >
    <div id="hex-grid" class="in-[.in-game]:hidden fixed inset-0 z-0 pointer-events-none overflow-hidden">
      <div
        id="background-layer"
        class="absolute inset-0 bg-cover bg-center"
        style="
          background-image: var(--background-image-url);
          background-position: center center;
          filter: saturate(1.15) contrast(1.05);
        "
      ></div>
      <div
        class="absolute inset-0"
        style="background: radial-gradient(circle at 50% 38%, rgba(10, 22, 40, 0.42) 0%, rgba(6, 11, 22, 0.86) 100%);"
      ></div>
    </div>

    <div
      id="mobile-menu-backdrop"
      class="hidden pointer-events-none"
      role="presentation"
      aria-hidden="true"
    ></div>

    <mobile-nav-bar id="sidebar-menu" class="hidden"></mobile-nav-bar>
    <lang-selector class="hidden"></lang-selector>

    <!-- MAIN CONTENT AREA -->
    <div
      class="in-[.in-game]:hidden flex-1 basis-full min-w-0 min-h-dvh in-[.page-open]:min-h-0 in-[.page-open]:overflow-hidden relative z-10 flex flex-col"
    >
      <desktop-nav-bar class="sticky top-0 z-[60]"></desktop-nav-bar>

      <div id="turnstile-container" class="hidden"></div>

      <main-layout class="contents">
        <play-page class="contents"></play-page>
        <single-player-modal
          id="page-single-player"
          inline
          class="hidden w-full h-full page-content relative z-50"
        ></single-player-modal>
        <user-setting
          id="page-settings"
          inline
          class="hidden w-full h-full page-content relative z-50"
        ></user-setting>
        <help-modal
          id="page-help"
          inline
          class="hidden w-full h-full page-content relative z-50"
        ></help-modal>
        <language-modal
          id="page-language"
          inline
          class="hidden w-full h-full page-content relative z-50"
        ></language-modal>
      </main-layout>
    </div>

    <!-- Game components -->
    <div id="app"></div>

    <!-- Bottom HUD -->
    <div
      id="bottom-hud-container"
      class="fixed bottom-0 left-0 w-full z-[500] flex flex-col items-center pointer-events-none"
      style="
        padding-bottom: env(safe-area-inset-bottom);
        padding-left: max(0.5rem, env(safe-area-inset-left));
        padding-right: max(0.5rem, env(safe-area-inset-right));
      "
    >
      <div
        class="flex flex-col pointer-events-none w-full z-10" style="max-width: 520px; margin: 0 auto;"
      >
        <attacks-display
          class="w-full pointer-events-auto"
        ></attacks-display>
        <tutorial-panel
          class="hidden w-full"
        ></tutorial-panel>
        <div
          class="pointer-events-auto bg-slate-900/92 border-t border-x border-white/15 backdrop-blur-md rounded-t-xl shadow-2xl"
        >
          <control-panel class="w-full"></control-panel>
          <unit-display class="block w-full overflow-x-auto"></unit-display>
        </div>
      </div>

      <div
        class="flex flex-col pointer-events-none items-end order-2 sm:order-none sm:flex-1 lg:col-start-3 lg:self-end lg:justify-end"
      >
        <chat-display
          class="w-full sm:w-auto pointer-events-auto"
        ></chat-display>
        <events-display
          class="w-full sm:w-auto pointer-events-auto"
        ></events-display>
        <actionable-events
          class="w-full sm:w-auto pointer-events-auto"
        ></actionable-events>
      </div>
    </div>

    <!-- Game modals and overlays -->
    <emoji-table></emoji-table>
    <build-menu></build-menu>
    <win-modal></win-modal>
    <new-lobby-prompt></new-lobby-prompt>
    <game-starting-modal></game-starting-modal>
    <div id="right-hud-container" class="flex flex-col items-end fixed top-0 right-0 z-1000 gap-2 pointer-events-none">
      <game-right-sidebar></game-right-sidebar>
      <replay-panel class="pointer-events-auto"></replay-panel>
    </div>
    <settings-modal></settings-modal>
    <user-setting id="game-settings"></user-setting>
    <player-panel></player-panel>
    <spawn-timer></spawn-timer>
    <immunity-timer></immunity-timer>
    <in-game-promo></in-game-promo>
    <alert-frame></alert-frame>
    <chat-modal></chat-modal>
    <multi-tab-modal></multi-tab-modal>
    <game-left-sidebar></game-left-sidebar>
    <performance-overlay></performance-overlay>
    <player-info-overlay></player-info-overlay>
    <heads-up-message></heads-up-message>

    <script src="./worker-inline.js"></script>
    <script src="./bundle.js"></script>
  </body>
</html>
"""

with open(os.path.join(dist, "index.html"), "w", encoding="utf-8") as f:
    f.write(index_html)

print("Generated dist/index.html and dist/worker-inline.js successfully!")
