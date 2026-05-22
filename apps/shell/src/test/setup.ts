import "@testing-library/jest-dom/vitest";

(HTMLCanvasElement.prototype.getContext as unknown as () => CanvasRenderingContext2D) = function () {
  return {
    beginPath: () => undefined,
    clearRect: () => undefined,
    lineTo: () => undefined,
    moveTo: () => undefined,
    stroke: () => undefined
  } as unknown as CanvasRenderingContext2D;
};
