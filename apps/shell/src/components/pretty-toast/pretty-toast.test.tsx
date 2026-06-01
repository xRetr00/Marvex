import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ToastProvider } from "./ToastProvider";
import { toast } from "./toast";

// Smoke test for the vendored react-native-pretty-toast web subset: confirms the
// DOM pill renders title + message in our Tauri-less (jsdom) environment, i.e. the
// react-native imports were stripped correctly and the queue presents a toast.
describe("vendored pretty-toast web pill", () => {
  it("presents a toast title and message", async () => {
    render(
      <ToastProvider>
        <div />
      </ToastProvider>,
    );

    act(() => {
      toast.show({ title: "Saved", message: "All good" });
    });

    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("All good")).toBeInTheDocument();
  });
});
