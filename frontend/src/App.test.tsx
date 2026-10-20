import {
  fireEvent,
  render,
  screen,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { RecordForm } from "./DataPage";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it("shows account validation when unauthenticated", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Sign in" }),
    }),
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <App />
    </QueryClientProvider>,
  );
  expect(
    await screen.findByRole("heading", { name: "A better week starts here." }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Sign in to TimeForge" }));
  expect(await screen.findByText("Enter your password")).toBeInTheDocument();
});
it("opens privacy and recovery with accessible controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Sign in" }),
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Forgot password?" }),
  );
  expect(
    screen.getByRole("heading", { name: "Let’s get you back in." }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Email address")).toHaveAttribute(
    "type",
    "email",
  );
});
it("preserves booleans and numeric foreign keys when saving a record", async () => {
  const save = vi.fn();
  render(
    <RecordForm
      schema={{
        properties: {
          name: { type: "string" },
          capacity: { type: "integer" },
          is_active: { type: "boolean", default: true },
        },
        required: ["name", "capacity"],
      }}
      onSave={save}
    />,
  );
  fireEvent.change(screen.getByLabelText("Name *"), {
    target: { value: "Lecture Hall" },
  });
  fireEvent.change(screen.getByLabelText("Capacity *"), {
    target: { value: "40" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save record" }));
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][0]).toEqual({
    name: "Lecture Hall",
    capacity: 40,
    is_active: true,
  });
});
