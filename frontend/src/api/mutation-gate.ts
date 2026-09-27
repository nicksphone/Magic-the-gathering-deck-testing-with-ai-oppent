// Single UI writer: reject overlapping intents rather than queue stale actions.
export function newMutationKey() {
  // getRandomValues is also available on plain HTTP LAN pages.
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
}

export function createMutationGate() {
  let busy = false;
  return {
    get busy() { return busy; },
    async run<T>(operation: () => Promise<T>): Promise<T> {
      if (busy) throw new Error("Another match operation is pending. Wait for it to finish.");
      busy = true;
      try { return await operation(); }
      finally { busy = false; }
    },
  };
}
