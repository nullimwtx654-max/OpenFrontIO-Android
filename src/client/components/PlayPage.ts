import { assetUrl } from "@openfront/shared/AssetUrls";
import { LitElement, html } from "lit";
import { customElement } from "lit/decorators.js";
import "./CosmeticBackground";
import "./NavUtilityIcons";

@customElement("play-page")
export class PlayPage extends LitElement {
  createRenderRoot() {
    return this;
  }

  render() {
    return html`
      <div
        id="page-play"
        class="flex flex-col w-full min-h-dvh justify-between"
        style="
          padding-top: max(0.5rem, env(safe-area-inset-top));
          padding-bottom: max(0.5rem, env(safe-area-inset-bottom));
          padding-left: max(1rem, env(safe-area-inset-left));
          padding-right: max(1rem, env(safe-area-inset-right));
        "
      >
        <!-- Unified Tactical Top Bar -->
        <header
          class="w-full max-w-6xl mx-auto flex items-center justify-between gap-3 px-4 py-2.5 rounded-2xl bg-slate-900/85 backdrop-blur-md border border-white/15 shadow-xl mb-3 shrink-0"
        >
          <!-- Brand Logo & Offline Badge -->
          <div class="flex items-center gap-3 min-w-0 shrink-0">
            <img
              src=${assetUrl("images/OpenFrontLogo.svg")}
              alt="OpenFront"
              class="h-6 sm:h-7 w-auto drop-shadow"
            />
            <span
              class="hidden sm:inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase tracking-widest bg-sky-500/20 text-sky-300 border border-sky-400/30"
            >
              Android Edition
            </span>
          </div>

          <!-- Commander Name Field (Centered/Compact) -->
          <div
            class="flex-1 max-w-xs sm:max-w-sm flex items-center bg-black/40 border border-white/15 rounded-xl px-2.5 py-1 min-w-0"
          >
            <svg
              class="w-4 h-4 text-sky-400 shrink-0 mr-2"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <username-input class="flex-1 min-w-0 h-8"></username-input>
          </div>

          <!-- Utility Actions: Language, Help, Settings -->
          <div class="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              data-open-language
              @click=${() => window.showPage?.("page-language")}
              class="flex items-center justify-center w-9 h-9 rounded-xl bg-white/5 hover:bg-white/15 border border-white/10 text-white/80 hover:text-white transition-all cursor-pointer"
              title="Language"
              aria-label="Language"
            >
              <svg class="w-4 h-4 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            </button>
            <button
              type="button"
              data-open-help
              @click=${() => window.showPage?.("page-help")}
              class="flex items-center justify-center w-9 h-9 rounded-xl bg-white/5 hover:bg-white/15 border border-white/10 text-white/80 hover:text-white transition-all cursor-pointer"
              title="How to Play"
              aria-label="How to Play"
            >
              <svg class="w-4 h-4 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </button>
            <button
              type="button"
              data-open-top-settings
              @click=${() => window.showPage?.("page-settings")}
              class="flex items-center justify-center w-9 h-9 rounded-xl bg-white/5 hover:bg-white/15 border border-white/10 text-white/80 hover:text-white transition-all cursor-pointer"
              title="Settings"
              aria-label="Settings"
            >
              <svg class="w-4 h-4 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
              </svg>
            </button>
          </div>
        </header>

        <!-- Main Command Deck -->
        <div class="flex-1 flex items-center justify-center w-full max-w-6xl mx-auto min-h-0">
          <game-mode-selector class="w-full"></game-mode-selector>
        </div>
      </div>
    `;
  }
}
