import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import * as fc from "fast-check";
import LoadingIndicator from "../LoadingIndicator";

/**
 * Feature: shadcn-ui-migration, Property 10: LoadingIndicator preserves accessibility attributes
 * Validates: Requirements 13.4
 *
 * For any non-empty message string, the rendered LoadingIndicator should have
 * role="status" and aria-label equal to the provided message.
 */
describe("Property 10: LoadingIndicator preserves accessibility attributes", () => {
  it("should have role='status' and aria-label matching the message for any non-empty string", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1 }).filter((s) => s.trim().length > 0),
        (message) => {
          const { container } = render(<LoadingIndicator message={message} />);
          const statusEl = container.querySelector('[role="status"]');

          expect(statusEl).not.toBeNull();
          expect(statusEl!.getAttribute("aria-label")).toBe(message);

          // cleanup
          container.remove();
        },
      ),
      { numRuns: 100 },
    );
  });
});
