import type { SavedGame } from "@openfront/shared/ApiSchemas";
import { html, LitElement, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import { ClientEnv } from "../ClientEnv";
import { showInGameConfirm } from "../InGameModal";
import {
  deleteSavedGame,
  exportSavedGameFile,
  importSavedGameFile,
  listSavedGames,
  type SavedGameError,
  updateSavedGame,
} from "../SavedGamesApi";
import {
  getMapName,
  renderDuration,
  showToast,
  translateText,
} from "../Utils";

export interface LoadSavedGameDetail {
  id: string;
  shared: boolean;
}

const SAVED_GAME_ID = /^[A-Za-z0-9_-]{1,64}$/;

export function savedGameIdFrom(input: string): string | null {
  const text = input.trim();
  if (SAVED_GAME_ID.test(text)) return text;
  try {
    const url = new URL(text);
    const id = new URLSearchParams(url.hash.slice(1)).get("save");
    return id !== null && SAVED_GAME_ID.test(id) ? id : null;
  } catch {
    return null;
  }
}

export function savedGameShareUrl(id: string): string {
  return `${ClientEnv.shareOrigin()}/#modal=single-player&save=${encodeURIComponent(id)}`;
}

@customElement("saved-games-panel")
export class SavedGamesPanel extends LitElement {
  @property({ type: Boolean }) signedIn = true;
  @property({ attribute: false }) sharedId: string | null = null;
  @property({ type: Boolean }) busy = false;

  @state() private expanded = true;
  @state() private saves: SavedGame[] | "loading" | "error" = [];
  @state() private renamingId: string | null = null;
  @state() private renameValue = "";
  @state() private pendingId: string | null = null;
  @state() private rowError: { id: string; message: string } | null = null;

  createRenderRoot() {
    return this;
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener("saved-games-changed", this.onSavesChanged);
    void this.refresh();
  }

  disconnectedCallback() {
    window.removeEventListener("saved-games-changed", this.onSavesChanged);
    super.disconnectedCallback();
  }

  private onSavesChanged = () => {
    void this.refresh();
  };

  protected willUpdate(changed: Map<string | number | symbol, unknown>) {
    if (changed.has("signedIn")) {
      void this.refresh();
    }
  }

  private expand() {
    if (this.expanded) return;
    this.expanded = true;
    void this.refresh();
  }

  private toggle() {
    if (this.expanded) this.expanded = false;
    else this.expand();
  }

  async refresh(): Promise<void> {
    const saves = await listSavedGames();
    this.saves = saves === false ? "error" : saves;
  }

  private load(id: string, shared: boolean) {
    this.dispatchEvent(
      new CustomEvent<LoadSavedGameDetail>("load-saved-game", {
        detail: { id, shared },
        bubbles: true,
        composed: true,
      }),
    );
  }

  private replace(updated: SavedGame) {
    if (!Array.isArray(this.saves)) return;
    this.saves = this.saves.map((s) => (s.id === updated.id ? updated : s));
  }

  private errorText(error: SavedGameError): string {
    if (error === "rejected") {
      return translateText("saved_games.error.name_invalid");
    }
    if (error === "not_found") {
      return translateText("saved_games.error.not_found");
    }
    return translateText("saved_games.error.request_failed");
  }

  private async run(
    save: SavedGame,
    work: () => Promise<SavedGame | SavedGameError>,
  ): Promise<boolean> {
    this.pendingId = save.id;
    this.rowError = null;
    try {
      const result = await work();
      if (typeof result === "string") {
        this.rowError = {
          id: save.id,
          message: this.errorText(result),
        };
        return false;
      }
      this.replace(result);
      return true;
    } finally {
      this.pendingId = null;
    }
  }

  private startRename(save: SavedGame) {
    this.renamingId = save.id;
    this.renameValue = save.name;
    this.rowError = null;
  }

  private async submitRename(save: SavedGame) {
    const name = this.renameValue.trim();
    if (name === "" || name === save.name) {
      this.renamingId = null;
      return;
    }
    const ok = await this.run(save, () => updateSavedGame(save.id, { name }));
    if (ok) this.renamingId = null;
  }

  private async handleExport(save: SavedGame) {
    const ok = await exportSavedGameFile(save.id);
    if (ok) {
      showToast(`Exported "${save.name}"`, "green");
    } else {
      showToast("Failed to export save file", "red");
    }
  }

  private handleImportClick() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,.ofsave";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const res = await importSavedGameFile(text);
        if (typeof res === "string") {
          showToast("Invalid save file format", "red");
        } else {
          showToast(`Imported save "${res.name}"`, "green");
          await this.refresh();
        }
      } catch {
        showToast("Failed to read save file", "red");
      }
    };
    input.click();
  }

  private async deleteSave(save: SavedGame) {
    const confirmed = await showInGameConfirm(
      translateText("saved_games.delete_confirm", { name: save.name }),
    );
    if (!confirmed) return;
    this.pendingId = save.id;
    this.rowError = null;
    try {
      const result = await deleteSavedGame(save.id);
      if (result === true || result === "not_found") {
        if (Array.isArray(this.saves)) {
          this.saves = this.saves.filter((s) => s.id !== save.id);
        }
        return;
      }
      this.rowError = {
        id: save.id,
        message: this.errorText(result),
      };
    } finally {
      this.pendingId = null;
    }
  }

  private details(save: SavedGame): string {
    return [
      getMapName(save.map) ?? save.map,
      renderDuration(save.tick / 10),
      new Date(save.updatedAt || save.createdAt).toLocaleString(),
    ].join(" · ");
  }

  private button(
    label: string,
    onClick: () => void,
    opts: { primary?: boolean; disabled?: boolean; attr?: string } = {},
  ): TemplateResult {
    const tone = opts.primary
      ? "bg-blue-600 hover:bg-blue-500 text-white"
      : "bg-white/5 hover:bg-white/10 text-white/80 border border-white/10";
    return html`<button
      type="button"
      class="px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${tone}"
      data-action=${opts.attr ?? ""}
      ?disabled=${opts.disabled ?? false}
      @click=${onClick}
    >
      ${label}
    </button>`;
  }

  private renderRow(save: SavedGame): TemplateResult {
    const pending = this.pendingId === save.id;
    const renaming = this.renamingId === save.id;
    const error = this.rowError?.id === save.id ? this.rowError.message : null;
    return html`<li
      class="flex flex-col gap-2 rounded-lg bg-white/5 border border-white/10 p-3"
      data-save-id=${save.id}
    >
      <div class="flex items-center gap-3">
        <div class="flex-1 min-w-0">
          ${
            renaming
              ? html`<input
                  class="w-full rounded-md bg-black/30 border border-white/20 px-2 py-1 text-sm text-white"
                  maxlength="64"
                  aria-label=${translateText("saved_games.rename")}
                  .value=${this.renameValue}
                  @input=${(e: Event) =>
                    (this.renameValue = (e.target as HTMLInputElement).value)}
                  @keydown=${(e: KeyboardEvent) => {
                    if (e.key === "Enter") void this.submitRename(save);
                    if (e.key === "Escape") {
                      e.stopPropagation();
                      this.renamingId = null;
                    }
                  }}
                />`
              : html`<div class="flex items-center gap-2">
                  <span class="font-semibold text-white truncate"
                    >${save.name}</span
                  >
                </div>`
          }
          <div class="text-xs text-white/50">${this.details(save)}</div>
        </div>
        ${this.button(
          translateText("saved_games.play"),
          () => this.load(save.id, false),
          { primary: true, disabled: this.busy || pending, attr: "play" },
        )}
      </div>
      <div class="flex flex-wrap gap-2">
        ${
          renaming
            ? html`${this.button(
                translateText("saved_games.rename_save"),
                () => void this.submitRename(save),
                { disabled: pending, attr: "rename-save" },
              )}
              ${this.button(
                translateText("common.cancel"),
                () => (this.renamingId = null),
                { disabled: pending },
              )}`
            : this.button(
                translateText("saved_games.rename"),
                () => this.startRename(save),
                { disabled: pending, attr: "rename" },
              )
        }
        ${this.button(
          "Export",
          () => void this.handleExport(save),
          { disabled: pending, attr: "export" },
        )}
        ${this.button(
          translateText("saved_games.delete"),
          () => void this.deleteSave(save),
          { disabled: pending, attr: "delete" },
        )}
      </div>
      ${
        error !== null
          ? html`<div class="text-xs text-red-400" data-row-error>
              ${error}
            </div>`
          : null
      }
    </li>`;
  }

  private renderOwn(): TemplateResult {
    const saves = this.saves;
    let body: TemplateResult;
    if (saves === "loading") {
      body = html`<div class="text-sm text-white/50">
        ${translateText("saved_games.loading")}
      </div>`;
    } else if (saves === "error") {
      body = html`<div class="text-sm text-red-400">
        ${translateText("saved_games.error.list_failed")}
      </div>`;
    } else if (saves.length === 0) {
      body = html`<div class="text-sm text-white/50" data-saves-empty>
        ${translateText("saved_games.empty")}
      </div>`;
    } else {
      body = html`<ul class="flex flex-col gap-2">
        ${saves.map((s) => this.renderRow(s))}
      </ul>`;
    }
    return html`<div data-own-saves>${body}</div>`;
  }

  render() {
    const expanded = this.expanded;
    const count = Array.isArray(this.saves) ? this.saves.length : 0;
    return html`<div class="w-full">
      <div class="flex items-center gap-2">
        <button
          type="button"
          aria-expanded=${expanded}
          data-saved-games-toggle
          @click=${this.toggle}
          class="flex-1 flex items-center justify-between gap-3 px-4 py-3 rounded-xl border text-sm font-bold text-white uppercase tracking-wider transition-all duration-200 active:scale-[0.99] ${
            expanded
              ? "bg-malibu-blue/20 border-malibu-blue/50"
              : "bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20"
          }"
        >
          <span class="flex items-center gap-3">
            <svg
              class="w-3.5 h-3.5 shrink-0 transition-transform duration-200 ${
                expanded ? "rotate-90" : ""
              }"
              viewBox="0 0 12 12"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M4 2l5 4-5 4z" />
            </svg>
            ${translateText("saved_games.title")}
          </span>
          <span class="px-2 py-0.5 rounded-full text-xs bg-blue-500/30 text-blue-200">
            ${count}
          </span>
        </button>
        <button
          type="button"
          data-import-save
          @click=${this.handleImportClick}
          class="px-4 py-3 rounded-xl border border-white/15 bg-white/5 hover:bg-white/10 text-xs font-bold text-white uppercase tracking-wider"
        >
          Import Save
        </button>
      </div>
      ${
        expanded
          ? html`<div class="mt-4 flex flex-col gap-4">
              ${this.renderOwn()}
            </div>`
          : null
      }
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "saved-games-panel": SavedGamesPanel;
  }
}
