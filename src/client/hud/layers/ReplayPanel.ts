import { EventBus } from "@openfront/shared/EventBus";
import { html, LitElement } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import { Controller } from "../../Controller";
import { ReplaySpeedChangeEvent } from "../../InputHandler";
import {
  defaultReplaySpeedMultiplier,
  ReplaySpeedMultiplier,
} from "../../utilities/ReplaySpeedMultiplier";
import { translateText } from "../../Utils";
import { GameView } from "../../view";

export class ShowReplayPanelEvent {
  constructor(
    public visible: boolean = true,
    public isSingleplayer: boolean = false,
  ) {}
}

@customElement("replay-panel")
export class ReplayPanel extends LitElement implements Controller {
  public game: GameView;
  public eventBus: EventBus;

  @property({ type: Boolean })
  visible: boolean = false;

  @state()
  private _replaySpeedMultiplier: number = defaultReplaySpeedMultiplier;

  @property({ type: Boolean })
  isSingleplayer = false;

  createRenderRoot() {
    return this; // Enable Tailwind CSS
  }

  init() {
    if (this.eventBus) {
      this.eventBus.on(ShowReplayPanelEvent, (event: ShowReplayPanelEvent) => {
        this.visible = event.visible;
        this.isSingleplayer = event.isSingleplayer;
      });
      this.eventBus.on(
        ReplaySpeedChangeEvent,
        (event: ReplaySpeedChangeEvent) => {
          this._replaySpeedMultiplier = event.replaySpeedMultiplier;
          this.requestUpdate();
        },
      );
    }
  }

  getTickIntervalMs() {
    return 1000;
  }

  tick() {
    if (!this.visible) return;
    this.requestUpdate();
  }

  onReplaySpeedChange(value: ReplaySpeedMultiplier) {
    this._replaySpeedMultiplier = value;
    this.eventBus?.emit(new ReplaySpeedChangeEvent(value));
  }

  render() {
    if (!this.visible) return html``;

    return html`
      <div
        class="pointer-events-auto p-2.5 bg-slate-900/95 border border-white/15 backdrop-blur-md shadow-xl rounded-l-lg" @pointerdown=${(e: Event) => e.stopPropagation()} @pointerup=${(e: Event) => e.stopPropagation()} @click=${(e: Event) => e.stopPropagation()}
        @contextmenu=${(e: Event) => e.preventDefault()}
      >
        <label class="block mb-2 text-white" translate="no">
          ${
            this.game?.config()?.isReplay()
              ? translateText("replay_panel.replay_speed")
              : translateText("replay_panel.game_speed")
          }
        </label>
        <div class="grid grid-cols-4 gap-2">
          ${this.renderSpeedButton(ReplaySpeedMultiplier.slow, "×0.5")}
          ${this.renderSpeedButton(ReplaySpeedMultiplier.normal, "×1")}
          ${this.renderSpeedButton(ReplaySpeedMultiplier.fast, "×2")}
          ${this.renderSpeedButton(
            ReplaySpeedMultiplier.fastest,
            translateText("replay_panel.fastest_game_speed"),
          )}
        </div>
      </div>
    `;
  }

  private renderSpeedButton(value: ReplaySpeedMultiplier, label: string) {
    const backgroundColor =
      this._replaySpeedMultiplier === value ? "bg-malibu-blue" : "";

    return html`
      <button
        class="pointer-events-auto cursor-pointer py-1.5 px-2.5 text-sm font-bold text-white rounded-md border transition border-gray-500 ${backgroundColor} hover:border-gray-200 active:scale-95"
        @click=${() => this.onReplaySpeedChange(value)}
      >
        ${label}
      </button>
    `;
  }
}
