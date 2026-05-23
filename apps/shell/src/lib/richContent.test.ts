import { describe, expect, it } from "vitest";
import { isTrivialReply, parseRichResponse } from "./richContent";

describe("richContent parser", () => {
  it("keeps greetings/short replies as a single plain text block", () => {
    expect(isTrivialReply("hi how are you")).toBe(true);
    const blocks = parseRichResponse("Hello! How can I help?");
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("text");
  });

  it("renders a product list as product cards for a product query", () => {
    const text = [
      "Here are the best laptops in 2026:",
      "1. Dell XPS 15 — $1,299 (4.5 stars)",
      "2. MacBook Air M4 — $999",
      "3. Lenovo Yoga — $1,099",
    ].join("\n");
    const blocks = parseRichResponse(text);
    const products = blocks.find((b) => b.type === "products");
    expect(products).toBeDefined();
    if (products && products.type === "products") {
      expect(products.products).toHaveLength(3);
      expect(products.products[0].title).toBe("Dell XPS 15");
      expect(products.products[0].price).toBe(1299);
      expect(products.products[0].rating).toBe(4.5);
    }
  });

  it("renders a numbered plan as a plan block", () => {
    const text = ["Here's the plan:", "1. Gather the files", "2. Summarize them", "3. Email the summary"].join("\n");
    const blocks = parseRichResponse(text);
    const plan = blocks.find((b) => b.type === "plan");
    expect(plan).toBeDefined();
    if (plan && plan.type === "plan") expect(plan.steps.length).toBe(3);
  });

  it("extracts markdown images as image cards", () => {
    const blocks = parseRichResponse("Here is the chart ![Q1 chart](https://example.com/c.png)");
    expect(blocks.some((b) => b.type === "image")).toBe(true);
  });

  it("treats a normal paragraph as plain text (no cards)", () => {
    const blocks = parseRichResponse("The capital of France is Paris, a major European city.");
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe("text");
  });
});
