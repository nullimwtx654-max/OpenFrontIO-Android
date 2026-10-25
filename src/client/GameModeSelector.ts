import { UserSettings } from "./UserSettings";
import {
  Difficulty,
  GameMapSize,
  GameMapType,
  GameMode,
  GameType,
} from "@openfront/engine-api/game/GameTypes";
import type { SnapshotHeader } from "@openfront/engine-api/game/SnapshotHeader";
import { assetUrl } from "@openfront/shared/AssetUrls";
import { generateID } from "@openfront/shared/SharedUtil";
import { html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";
import "./components/SavedGamesPanel";
import type { LoadSavedGameDetail } from "./components/SavedGamesPanel";
import type { DesktopSessionState, DesktopUpdateState } from "./DesktopShell";
import { showInGameAlert } from "./InGameModal";
import { whenModalLoaded } from "./LazyModals";
import { JoinLobbyEvent } from "./Main";
import { fallbackPlayerName } from "./PlayerName";
import { downloadSavedGame } from "./SavedGamesApi";
import type { SinglePlayerModal } from "./SinglePlayerModal";
import { UsernameInput } from "./UsernameInput";
import { translateText } from "./Utils";

export function multiplayerAllowedForBackend(_backendOutage: boolean): boolean {
  return false;
}

export function shouldBlockMultiplayerAction(
  _update: DesktopUpdateState | null,
  _session: DesktopSessionState | null,
  _backendOutage: boolean,
): boolean {
  return true;
}

export function lobbyFeedSuspended(
  _session: DesktopSessionState | null,
): boolean {
  return true;
}

export function shouldBlockSocketSourcedAction(
  _update: DesktopUpdateState | null,
  _session: DesktopSessionState | null,
): boolean {
  return true;
}

export function joinIsGateable(_lobby: any): boolean {
  return false;
}

export function shouldBlockJoin(
  _lobby: any,
  _update: DesktopUpdateState | null,
  _session: DesktopSessionState | null,
): boolean {
  return false;
}

export function reportMultiplayerRefusal(_backendOutage: boolean): void {}

@customElement("game-mode-selector")
export class GameModeSelector extends LitElement {
  @state() private inputValid = true;
  @state() private startingSave = false;

  createRenderRoot() {
    return this;
  }

  public start(): void {}
  public stop(): void {}

  private getUsername(): string {
    const input = document.querySelector("username-input") as UsernameInput | null;
    return input?.resolvedName()?.name || fallbackPlayerName().name || "Commander";
  }

  private openSinglePlayerModal = () => {
    if (window.showPage) {
      window.showPage("page-single-player");
    }
    whenModalLoaded("single-player-modal", () =>
      (
        document.querySelector("single-player-modal") as SinglePlayerModal
      )?.open(),
    );
  };

  private startQuickGame = () => {
    try { new UserSettings().setTutorialDismissed(true); } catch {}
    const clientID = generateID();
    const gameID = generateID();
    const username = this.getUsername();
    const detail: JoinLobbyEvent = {
      gameID,
      source: "singleplayer",
      gameStartInfo: {
        gameID,
        lobbyCreatedAt: Date.now(),
        players: [
          {
            clientID,
            username,
            clanTag: null,
            cosmetics: {},
          },
        ],
        config: {
          gameMap: GameMapType.World,
          gameMapSize: GameMapSize.Compact,
          gameType: GameType.Singleplayer,
          gameMode: GameMode.FFA,
          difficulty: Difficulty.Easy,
          bots: 100,
          nations: "default",
          infiniteGold: false,
          infiniteTroops: false,
          instantBuild: false,
          randomSpawn: false,
          donateGold: false,
          donateTroops: false,
          disabledUnits: [],
        },
      },
    };
    document.dispatchEvent(
      new CustomEvent("join-lobby", {
        detail,
        bubbles: true,
        composed: true,
      }),
    );
  };

  private startTutorial = () => {
    document.dispatchEvent(new CustomEvent("start-tutorial"));
  };

  private handleLoadSavedGame = async (e: Event) => {
    if (this.startingSave) return;
    const { id } = (e as CustomEvent<LoadSavedGameDetail>).detail;
    this.startingSave = true;
    try {
      const snapshot = await downloadSavedGame(id, false);
      if (typeof snapshot === "string") {
        await showInGameAlert(translateText("saved_games.error.not_found"));
        return;
      }
      const { readSnapshotHeader } = await import("./WorkerClient");
      let header: SnapshotHeader;
      try {
        header = await readSnapshotHeader(snapshot);
      } catch (err) {
        console.warn("Saved game unreadable:", err);
        await showInGameAlert(translateText("saved_games.error.unreadable"));
        return;
      }
      const human = header.humans[0];
      const gameID = generateID();
      const detail: JoinLobbyEvent = {
        gameID,
        source: "singleplayer",
        snapshot,
        gameStartInfo: {
          gameID,
          lobbyCreatedAt: Date.now(),
          players: [
            {
              clientID: human?.clientID ?? generateID(),
              username: this.getUsername(),
              clanTag: null,
              cosmetics: {},
            },
          ],
          config: header.gameConfig,
        },
      };
      document.dispatchEvent(
        new CustomEvent("join-lobby", {
          detail,
          bubbles: true,
          composed: true,
        }),
      );
    } catch (err) {
      console.error("Failed to load saved game:", err);
      await showInGameAlert(translateText("saved_games.error.load_failed"));
    } finally {
      this.startingSave = false;
    }
  };

  render() {
    return html`
      <div class="grid grid-cols-1 sm:grid-cols-12 gap-3.5 w-full items-stretch">
        <!-- Left Column: Primary & Secondary Game Modes (7 cols on landscape) -->
        <div class="sm:col-span-7 flex flex-col gap-3 justify-between">
          <!-- Hero Card: Custom Solo Campaign -->
          <button
            type="button"
            data-open-solo
            @click=${this.openSinglePlayerModal}
            style="background: linear-gradient(135deg, rgba(2,132,199,0.92) 0%, rgba(15,23,42,0.95) 100%);"
            class="group relative overflow-hidden flex items-center justify-between gap-4 p-4 sm:p-5 rounded-2xl border border-sky-400/40 shadow-xl text-left text-white transition-all active:scale-[0.99] cursor-pointer"
          >
            <div class="flex items-center gap-3.5 min-w-0 z-10">
              <div class="flex items-center justify-center w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-sky-400/20 border border-sky-300/30 shrink-0 shadow-md">
                <svg class="w-7 h-7 text-sky-300 pointer-events-none" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7z" />
                </svg>
              </div>
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-lg sm:text-2xl font-extrabold uppercase tracking-wider text-white">
                    ${translateText("main.solo") || "Solo Campaign"}
                  </span>
                  <span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest bg-sky-400/25 text-sky-200 border border-sky-300/30">
                    135 Maps
                  </span>
                </div>
                <div class="text-xs sm:text-sm text-sky-100/80 mt-1 leading-snug">
                  Choose any map, difficulty, bot count, nations & custom modifiers
                </div>
              </div>
            </div>
            <img
              src=${assetUrl("maps/world/thumbnail.webp")}
              alt=""
              class="hidden sm:block w-24 h-14 object-cover rounded-xl border border-white/20 opacity-85 shrink-0 pointer-events-none shadow"
            />
          </button>

          <!-- Action Row: Quick Battle, Tutorial, Settings -->
          <div class="grid grid-cols-3 gap-2.5 sm:gap-3">
            <button
              type="button"
              data-quick-play
              @click=${this.startQuickGame}
              style="background: linear-gradient(135deg, rgba(5,150,105,0.9) 0%, rgba(6,78,59,0.95) 100%);"
              class="flex flex-col items-start justify-between p-3 sm:p-3.5 rounded-2xl border border-emerald-400/35 text-left text-white shadow-lg transition-all active:scale-[0.98] cursor-pointer"
            >
              <div class="flex items-center gap-2">
                <img src=${assetUrl("images/SwordIconWhite.svg")} alt="" class="w-4 h-4 opacity-90 pointer-events-none" />
                <span class="text-xs sm:text-sm font-extrabold uppercase tracking-wider">
                  Quick Battle
                </span>
              </div>
              <div class="text-[11px] text-emerald-100/80 mt-1 leading-tight">
                Instant World · 100 Bots
              </div>
            </button>

            <button
              type="button"
              data-start-tutorial
              @click=${this.startTutorial}
              style="background: linear-gradient(135deg, rgba(217,119,6,0.9) 0%, rgba(120,53,15,0.95) 100%);"
              class="flex flex-col items-start justify-between p-3 sm:p-3.5 rounded-2xl border border-amber-400/35 text-left text-white shadow-lg transition-all active:scale-[0.98] cursor-pointer"
            >
              <div class="flex items-center gap-2">
                <img src=${assetUrl("images/InfoIcon.svg")} alt="" class="w-4 h-4 opacity-90 pointer-events-none" />
                <span class="text-xs sm:text-sm font-extrabold uppercase tracking-wider">
                  ${translateText("main.tutorial") || "Tutorial"}
                </span>
              </div>
              <div class="text-[11px] text-amber-100/80 mt-1 leading-tight">
                Guided Training Match
              </div>
            </button>

            <button
              type="button"
              data-open-home-settings
              @click=${() => window.showPage?.("page-settings")}
              class="flex flex-col items-start justify-between p-3 sm:p-3.5 rounded-2xl bg-slate-900/90 hover:bg-slate-800 border border-white/15 text-left text-white shadow-lg transition-all active:scale-[0.98] cursor-pointer"
            >
              <div class="flex items-center gap-2">
                <img src=${assetUrl("images/SettingIconWhite.svg")} alt="" class="w-4 h-4 opacity-90 pointer-events-none" />
                <span class="text-xs sm:text-sm font-extrabold uppercase tracking-wider">
                  Settings
                </span>
              </div>
              <div class="text-[11px] text-white/65 mt-1 leading-tight">
                Controls & Graphics
              </div>
            </button>
          </div>
        </div>

        <!-- Right Column: Local Saved Games Vault (5 cols on landscape) -->
        <div class="sm:col-span-5 flex flex-col rounded-2xl bg-slate-900/85 backdrop-blur-md border border-white/15 p-3.5 shadow-xl min-h-[180px] max-h-[260px] overflow-y-auto">
          <saved-games-panel
            .signedIn=${true}
            .busy=${this.startingSave}
            @load-saved-game=${this.handleLoadSavedGame}
          ></saved-games-panel>
        </div>
      </div>
    `;
  }
}
