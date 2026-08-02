function normalized(value, direction, absolute) {
  if (!Number.isFinite(value)) {
    return direction === "asc" ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
  }
  return absolute ? Math.abs(value) : value;
}

self.addEventListener("message", (event) => {
  const message = event.data || {};
  if (message.type !== "sort") return;
  try {
    const values = new Float64Array(message.values);
    const ids = message.ids ? new Uint32Array(message.ids) : null;
    const direction = message.direction === "asc" ? "asc" : "desc";
    const absolute = Boolean(message.absolute);
    const positions = new Uint32Array(values.length);
    for (let index = 0; index < positions.length; index += 1) positions[index] = index;
    positions.sort((left, right) => {
      const a = normalized(values[left], direction, absolute);
      const b = normalized(values[right], direction, absolute);
      if (a === b) {
        const leftId = ids ? ids[left] : left;
        const rightId = ids ? ids[right] : right;
        return leftId - rightId;
      }
      return direction === "asc" ? a - b : b - a;
    });
    const output = new Uint32Array(positions.length);
    for (let index = 0; index < positions.length; index += 1) {
      output[index] = ids ? ids[positions[index]] : positions[index];
    }
    self.postMessage({ type: "sorted", indexes: output }, [output.buffer]);
  } catch (error) {
    self.postMessage({
      type: "error",
      error: error instanceof Error ? error.message : String(error),
    });
  }
});
