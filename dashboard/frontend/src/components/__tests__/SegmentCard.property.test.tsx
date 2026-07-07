import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import * as fc from "fast-check";
import SegmentCard from "../SegmentCard";
import { formatTimeShort } from "../../utils/formatTime";
import type { DviSegment } from "../../types";

/**
 * Feature: shadcn-ui-migration, Property 4: SegmentCard preserves interactive ARIA attributes
 * Validates: Requirements 6.4
 *
 * For any DviSegment object and active state (boolean), the rendered SegmentCard
 * should have role="button", tabIndex=0, and an aria-label containing the
 * formatted start and end times of the segment.
 */
describe("Property 4: SegmentCard preserves interactive ARIA attributes", () => {
  const dviSegmentArb = fc
    .record({
      start: fc.nat({ max: 86400 }),
      end: fc.nat({ max: 86400 }),
      duration: fc.float({ min: 0, max: 3600, noNaN: true }),
      dvi_text: fc.string({ minLength: 0, maxLength: 200 }),
    })
    .map((r) => ({
      ...r,
      end: Math.max(r.start, r.end),
    })) as fc.Arbitrary<DviSegment>;

  it("should have role='button', tabIndex=0, and aria-label with formatted start/end times for any segment and active state", () => {
    fc.assert(
      fc.property(dviSegmentArb, fc.boolean(), (segment, isActive) => {
        const onClick = vi.fn();
        const { container } = render(
          <SegmentCard
            segment={segment}
            isActive={isActive}
            onClick={onClick}
          />,
        );

        const buttonEl = container.querySelector('[role="button"]');
        expect(buttonEl).not.toBeNull();
        expect(buttonEl!.getAttribute("tabindex")).toBe("0");

        const ariaLabel = buttonEl!.getAttribute("aria-label");
        expect(ariaLabel).not.toBeNull();
        expect(ariaLabel).toContain(formatTimeShort(segment.start));
        expect(ariaLabel).toContain(formatTimeShort(segment.end));

        container.remove();
      }),
      { numRuns: 100 },
    );
  });
});
