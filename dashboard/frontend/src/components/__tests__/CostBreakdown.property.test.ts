import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { formatCost, groupByService } from "../CostBreakdownTable";
import type { ServiceCostItem } from "../../types";

/**
 * Feature: shadcn-ui-migration, Property 5: formatCost produces 6-decimal-place string
 * Validates: Requirements 7.5
 *
 * For any non-negative number, formatCost(n) should return a string
 * representation with exactly 6 decimal places.
 */
describe("Property 5: formatCost produces 6-decimal-place string", () => {
  it("should return a string with exactly 6 decimal places for any non-negative number", () => {
    fc.assert(
      fc.property(fc.float({ min: 0, max: 1_000_000, noNaN: true }), (n) => {
        const result = formatCost(n);
        // Must be a string
        expect(typeof result).toBe("string");
        // Must contain a decimal point
        expect(result).toContain(".");
        // Decimal portion must be exactly 6 digits
        const parts = result.split(".");
        expect(parts).toHaveLength(2);
        expect(parts[1]).toHaveLength(6);
        // Must match the numeric value formatted to 6 decimal places
        expect(result).toBe(n.toFixed(6));
      }),
      { numRuns: 100 },
    );
  });
});

/**
 * Feature: shadcn-ui-migration, Property 6: groupByService preserves all items and groups by service
 * Validates: Requirements 7.5
 *
 * For any array of ServiceCostItem objects, groupByService(items) should return
 * an array of the same length containing the same items, where items with the
 * same service field are adjacent.
 */
describe("Property 6: groupByService preserves all items and groups by service", () => {
  const serviceCostItemArb: fc.Arbitrary<ServiceCostItem> = fc.record({
    service: fc.string({ minLength: 1, maxLength: 20 }),
    description: fc.string({ minLength: 0, maxLength: 50 }),
    usage: fc.string({ minLength: 0, maxLength: 30 }),
    cost_usd: fc.float({ min: 0, max: 100_000, noNaN: true }),
  });

  it("should return an array of the same length as the input", () => {
    fc.assert(
      fc.property(
        fc.array(serviceCostItemArb, { minLength: 0, maxLength: 30 }),
        (items) => {
          const result = groupByService(items);
          expect(result).toHaveLength(items.length);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("should preserve all items (same elements, possibly reordered)", () => {
    fc.assert(
      fc.property(
        fc.array(serviceCostItemArb, { minLength: 0, maxLength: 30 }),
        (items) => {
          const result = groupByService(items);
          // Every item in the input must appear in the output
          for (const item of items) {
            expect(result).toContainEqual(item);
          }
          // Every item in the output must appear in the input
          for (const item of result) {
            expect(items).toContainEqual(item);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it("should group items so that items with the same service are adjacent", () => {
    fc.assert(
      fc.property(
        fc.array(serviceCostItemArb, { minLength: 0, maxLength: 30 }),
        (items) => {
          const result = groupByService(items);
          // For each service, all indices should be contiguous
          const serviceIndices = new Map<string, number[]>();
          result.forEach((item, idx) => {
            const indices = serviceIndices.get(item.service);
            if (indices) {
              indices.push(idx);
            } else {
              serviceIndices.set(item.service, [idx]);
            }
          });
          for (const [, indices] of serviceIndices) {
            // Indices should be consecutive (no gaps)
            for (let i = 1; i < indices.length; i++) {
              expect(indices[i]).toBe(indices[i - 1] + 1);
            }
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
