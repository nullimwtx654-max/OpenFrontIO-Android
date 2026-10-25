import { type SavedGame } from "@openfront/shared/ApiSchemas";

export const MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024;

export type SavedGameError =
  | "unauthorized"
  | "limit"
  | "rejected"
  | "not_found"
  | "request_failed";

interface AndroidBridgeInterface {
  saveGame?: (id: string, metaJson: string, base64Data: string) => boolean;
  loadGame?: (id: string) => string | null;
  listGames?: () => string;
  deleteGame?: (id: string) => boolean;
  renameGame?: (id: string, newName: string) => string | null;
}

declare global {
  interface Window {
    AndroidBridge?: AndroidBridgeInterface;
  }
}

const META_STORAGE_KEY = "openfront.android.saved_games.v1";
const DATA_PREFIX = "openfront.android.save_blob.";
const IDB_NAME = "OpenFrontAndroidSavesDB";
const IDB_STORE = "snapshots";

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(
      null,
      Array.from(bytes.subarray(i, i + chunk)),
    );
  }
  return btoa(binary);
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) {
    out[i] = bin.charCodeAt(i);
  }
  return out;
}

function openSavesDB(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open(IDB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(IDB_STORE)) {
          db.createObjectStore(IDB_STORE);
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

async function idbPut(id: string, bytes: Uint8Array): Promise<boolean> {
  const db = await openSavesDB();
  if (!db) return false;
  return new Promise((resolve) => {
    try {
      const tx = db.transaction(IDB_STORE, "readwrite");
      tx.objectStore(IDB_STORE).put(bytes, id);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => resolve(false);
    } catch {
      resolve(false);
    }
  });
}

async function idbGet(id: string): Promise<Uint8Array | null> {
  const db = await openSavesDB();
  if (!db) return null;
  return new Promise((resolve) => {
    try {
      const tx = db.transaction(IDB_STORE, "readonly");
      const req = tx.objectStore(IDB_STORE).get(id);
      req.onsuccess = () => {
        const res = req.result;
        if (res instanceof Uint8Array) resolve(res);
        else if (res instanceof ArrayBuffer) resolve(new Uint8Array(res));
        else resolve(null);
      };
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

async function idbDelete(id: string): Promise<void> {
  const db = await openSavesDB();
  if (!db) return;
  return new Promise((resolve) => {
    try {
      const tx = db.transaction(IDB_STORE, "readwrite");
      tx.objectStore(IDB_STORE).delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
    } catch {
      resolve();
    }
  });
}

function readLocalMetaList(): SavedGame[] {
  try {
    if (window.AndroidBridge?.listGames) {
      const nativeJson = window.AndroidBridge.listGames();
      if (nativeJson) {
        const parsed = JSON.parse(nativeJson);
        if (Array.isArray(parsed) && parsed.length > 0) {
          localStorage.setItem(META_STORAGE_KEY, JSON.stringify(parsed));
          return parsed;
        }
      }
    }
  } catch (e) {
    console.warn("AndroidBridge.listGames failed, falling back to localStorage", e);
  }
  try {
    const raw = localStorage.getItem(META_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeLocalMetaList(saves: SavedGame[]): void {
  try {
    localStorage.setItem(META_STORAGE_KEY, JSON.stringify(saves));
  } catch (e) {
    console.warn("Failed to write save metadata to localStorage", e);
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("saved-games-changed", { detail: saves }));
  }
}

export async function listSavedGames(): Promise<SavedGame[] | false> {
  const list = readLocalMetaList();
  list.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
  return list;
}

export async function uploadSavedGame(
  snapshot: Uint8Array,
  meta: { name: string; map: string; tick: number; id?: string },
): Promise<SavedGame | SavedGameError> {
  try {
    const cleanName = (meta.name || "Saved Game").trim().slice(0, 64);
    if (!cleanName) return "rejected";

    const now = new Date().toISOString();
    const saves = readLocalMetaList();
    const id = meta.id || `save_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const existingIdx = saves.findIndex((s) => s.id === id);
    const record: SavedGame = {
      id,
      name: cleanName,
      map: meta.map,
      tick: Math.max(0, Math.floor(meta.tick)),
      public: false,
      createdAt: existingIdx >= 0 ? saves[existingIdx].createdAt : now,
      updatedAt: now,
    };

    let storedBytes: Uint8Array = snapshot;
    let isGzipped = false;
    try {
      storedBytes = await gzip(snapshot);
      isGzipped = true;
    } catch {
      storedBytes = snapshot;
      isGzipped = false;
    }

    // Tag header with whether it's gzipped or raw
    const b64 = bytesToBase64(storedBytes);
    const payloadStr = (isGzipped ? "GZ:" : "RAW:") + b64;

    // 1. Save via Android Native Bridge if available
    try {
      if (window.AndroidBridge?.saveGame) {
        window.AndroidBridge.saveGame(id, JSON.stringify(record), payloadStr);
      }
    } catch (e) {
      console.warn("AndroidBridge.saveGame error:", e);
    }

    // 2. Save in IndexedDB
    await idbPut(id, snapshot);

    // 3. Also attempt localStorage fallback for smaller saves
    try {
      if (payloadStr.length < 2_500_000) {
        localStorage.setItem(DATA_PREFIX + id, payloadStr);
      }
    } catch {
      // Ignore quota errors on localStorage since IDB / AndroidBridge holds the binary
    }

    if (existingIdx >= 0) {
      saves[existingIdx] = record;
    } else {
      saves.unshift(record);
    }
    writeLocalMetaList(saves);
    return record;
  } catch (err) {
    console.error("uploadSavedGame failed:", err);
    return "request_failed";
  }
}

export async function updateSavedGame(
  id: string,
  update: { name?: string; public?: boolean },
): Promise<SavedGame | SavedGameError> {
  try {
    const saves = readLocalMetaList();
    const idx = saves.findIndex((s) => s.id === id);
    if (idx < 0) return "not_found";
    if (update.name !== undefined) {
      const trimmed = update.name.trim().slice(0, 64);
      if (!trimmed) return "rejected";
      saves[idx].name = trimmed;
    }
    if (update.public !== undefined) {
      saves[idx].public = update.public;
    }
    saves[idx].updatedAt = new Date().toISOString();
    try {
      if (window.AndroidBridge?.renameGame && update.name) {
        window.AndroidBridge.renameGame(id, saves[idx].name);
      }
    } catch {}
    writeLocalMetaList(saves);
    return saves[idx];
  } catch {
    return "request_failed";
  }
}

export async function deleteSavedGame(
  id: string,
): Promise<true | SavedGameError> {
  try {
    const saves = readLocalMetaList();
    const next = saves.filter((s) => s.id !== id);
    try {
      if (window.AndroidBridge?.deleteGame) {
        window.AndroidBridge.deleteGame(id);
      }
    } catch {}
    await idbDelete(id);
    try {
      localStorage.removeItem(DATA_PREFIX + id);
    } catch {}
    writeLocalMetaList(next);
    return true;
  } catch {
    return "request_failed";
  }
}

export async function fetchSharedSavedGame(
  id: string,
): Promise<SavedGame | SavedGameError> {
  const saves = readLocalMetaList();
  const found = saves.find((s) => s.id === id);
  return found ?? "not_found";
}

export async function downloadSavedGame(
  id: string,
  _shared: boolean = false,
): Promise<Uint8Array | SavedGameError> {
  try {
    // 1. Try IndexedDB first (stores raw uncompressed Uint8Array)
    const fromIdb = await idbGet(id);
    if (fromIdb && fromIdb.byteLength > 0) {
      return fromIdb;
    }

    // 2. Try AndroidBridge native file storage
    let payloadStr: string | null = null;
    if (window.AndroidBridge?.loadGame) {
      try {
        payloadStr = window.AndroidBridge.loadGame(id);
      } catch (e) {
        console.warn("AndroidBridge.loadGame failed:", e);
      }
    }

    // 3. Fallback to localStorage
    if (!payloadStr) {
      payloadStr = localStorage.getItem(DATA_PREFIX + id);
    }
    if (!payloadStr) return "not_found";

    if (payloadStr.startsWith("GZ:")) {
      const compressed = base64ToBytes(payloadStr.slice(3));
      return await gunzip(compressed);
    } else if (payloadStr.startsWith("RAW:")) {
      return base64ToBytes(payloadStr.slice(4));
    } else {
      return base64ToBytes(payloadStr);
    }
  } catch (err) {
    console.error("downloadSavedGame failed:", err);
    return "request_failed";
  }
}

export async function exportSavedGameFile(id: string): Promise<boolean> {
  try {
    const saves = readLocalMetaList();
    const meta = saves.find((s) => s.id === id);
    if (!meta) return false;
    const snap = await downloadSavedGame(id, false);
    if (typeof snap === "string") return false;
    const b64 = bytesToBase64(snap);
    const bundle = JSON.stringify({
      format: "openfront-android-save-v1",
      meta,
      snapshotBase64: b64,
    });
    const blob = new Blob([bundle], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeName = meta.name.replace(/[^a-zA-Z0-9_-]+/g, "_");
    a.download = `${safeName}.ofsave.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    return true;
  } catch (e) {
    console.error("Failed to export save:", e);
    return false;
  }
}

export async function importSavedGameFile(fileText: string): Promise<SavedGame | SavedGameError> {
  try {
    const parsed = JSON.parse(fileText);
    if (!parsed || !parsed.meta || typeof parsed.snapshotBase64 !== "string") {
      return "rejected";
    }
    const bytes = base64ToBytes(parsed.snapshotBase64);
    return await uploadSavedGame(bytes, {
      name: String(parsed.meta.name || "Imported Save"),
      map: String(parsed.meta.map || "World"),
      tick: Number(parsed.meta.tick || 0),
    });
  } catch (e) {
    console.error("Failed to import save:", e);
    return "rejected";
  }
}

export async function gzip(
  bytes: Uint8Array,
): Promise<Uint8Array<ArrayBuffer>> {
  if (typeof CompressionStream === "undefined") {
    return bytes as Uint8Array<ArrayBuffer>;
  }
  return readAll(
    streamOf(bytes).pipeThrough(new CompressionStream("gzip")),
    Infinity,
  );
}

export async function gunzip(
  bytes: Uint8Array,
  max = MAX_SNAPSHOT_BYTES,
): Promise<Uint8Array<ArrayBuffer>> {
  if (typeof DecompressionStream === "undefined") {
    return bytes as Uint8Array<ArrayBuffer>;
  }
  return readAll(
    streamOf(bytes).pipeThrough(new DecompressionStream("gzip")),
    max,
  );
}

function streamOf(bytes: Uint8Array): ReadableStream<BufferSource> {
  return new ReadableStream<BufferSource>({
    start(controller) {
      controller.enqueue(bytes as BufferSource);
      controller.close();
    },
  });
}

async function readAll(
  stream: ReadableStream<Uint8Array>,
  max: number,
): Promise<Uint8Array<ArrayBuffer>> {
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > max) throw new Error("Snapshot is too large");
      chunks.push(value);
    }
  } finally {
    reader.cancel().catch(() => {});
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return out;
}
