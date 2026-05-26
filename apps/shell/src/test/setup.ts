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

class TestResizeObserver {
  constructor(private readonly callback: ResizeObserverCallback) {}
  observe(target: Element) {
    this.callback([{ target, contentRect: { width: 900, height: 360 } as DOMRectReadOnly } as ResizeObserverEntry], this as unknown as ResizeObserver);
  }
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = TestResizeObserver as unknown as typeof ResizeObserver;
