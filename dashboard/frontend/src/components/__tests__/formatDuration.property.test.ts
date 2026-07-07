import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { formatDuration } from "../CostReportView";

/**
 * Feature: shadcn-ui-migration, Property 9: formatDuration produces correct minute/second string
 * Validates: Requirements 12.4
 *
 * For any non-negative number of seconds, formatDuration(seconds) should return
 * a string in the format `{m}m {s}s` where m = floor(seconds / 60) and s = round(seconds % 60).
 */
describe("Property 9: formatDuration produces correct minute/second string", () => {
  it("should return '{m}m {s}s' where m = floor(seconds/60) and s = round(seconds%60) for any non-negative seconds", () => {
    fc.assert(
      fc.property(
        fc.float({ min: 0, max: 1_000_000, noNaN: true }),
        (seconds) => {
          const result = formatDuration(seconds);
          const expectedM = Math.floor(seconds / 60);
          const expectedS = Math.round(seconds % 60);
          expect(result).toBe(`${expectedM}m ${expectedS}s`);
        },
      ),
      { numRuns: 100 },
    );
  });
});
