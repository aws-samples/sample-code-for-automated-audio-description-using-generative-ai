import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import * as fc from "fast-check";
import TriggerButton from "../TriggerButton";

/**
 * Feature: shadcn-ui-migration, Property 3: TriggerButton disabled state is correct for all prop combinations
 * Validates: Requirements 5.5
 *
 * For any combination of `disabled` (boolean) and `loading` (boolean) props,
 * the rendered button element's `disabled` attribute should be `true` when either
 * `disabled` or `loading` is `true`, and the `onClick` handler should only be
 * invocable when the button is not disabled.
 */
describe("Property 3: TriggerButton disabled state is correct for all prop combinations", () => {
  it("button is disabled when either disabled or loading is true, enabled only when both are false", () => {
    fc.assert(
      fc.property(fc.boolean(), fc.boolean(), (disabled, loading) => {
        const onClick = vi.fn();
        const { container } = render(
          <TriggerButton
            disabled={disabled}
            loading={loading}
            onClick={onClick}
          />,
        );

        const button = container.querySelector("button")!;
        const shouldBeDisabled = disabled || loading;

        expect(button.disabled).toBe(shouldBeDisabled);

        // Attempt to click the button
        fireEvent.click(button);

        if (shouldBeDisabled) {
          expect(onClick).not.toHaveBeenCalled();
        } else {
          expect(onClick).toHaveBeenCalledTimes(1);
        }

        container.remove();
      }),
      { numRuns: 100 },
    );
  });
});
