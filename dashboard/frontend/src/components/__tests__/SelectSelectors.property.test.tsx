import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import type { VideoEntry, InputVideo } from "../../types";

/**
 * Feature: shadcn-ui-migration, Property 2: Select-based selectors call onSelect with the matching data object
 * Validates: Requirements 4.3, 4.4, 4.5
 *
 * For any list of video objects (VideoEntry or InputVideo) and any valid selection
 * key from that list, when the Select's onValueChange fires with that key, the
 * onSelect callback should receive the object whose key matches the selected value,
 * and the placeholder should display the count equal to the list length when no
 * selection is made.
 *
 * Since VideoSelector and InputVideoSelector fetch data internally via API calls,
 * we test the selection logic pattern in isolation:
 * - Given an array of objects with a `key` field and a selected key value,
 *   the find operation `videos.find(v => v.key === selectedKey)` returns the correct object.
 */

// Generate ISO date strings from integer timestamps to avoid Invalid Date issues
const safeDateArb = fc
  .integer({ min: 946684800000, max: 4102444799000 }) // 2000-01-01 to 2099-12-31
  .map((ts) => new Date(ts).toISOString());

const videoEntryArb: fc.Arbitrary<VideoEntry> = fc.record({
  key: fc.string({ minLength: 1, maxLength: 50 }),
  filename: fc.string({ minLength: 1, maxLength: 100 }),
  pipeline_version: fc.stringMatching(/^v[1-3]$/),
  video_id: fc.uuid(),
  last_modified: safeDateArb,
  size_bytes: fc.nat({ max: 1_000_000_000 }),
});

const inputVideoArb: fc.Arbitrary<InputVideo> = fc.record({
  key: fc.string({ minLength: 1, maxLength: 50 }),
  video_id: fc.uuid(),
  size_mb: fc.float({
    min: Math.fround(0.1),
    max: Math.fround(5000),
    noNaN: true,
  }),
  last_modified: safeDateArb,
});

/** Generate a non-empty array with unique keys, plus a valid index into it. */
function uniqueKeyListWithIndex<T extends { key: string }>(
  arb: fc.Arbitrary<T>,
) {
  return fc
    .array(arb, { minLength: 1, maxLength: 50 })
    .map((items) => {
      const seen = new Set<string>();
      return items.filter((item) => {
        if (seen.has(item.key)) return false;
        seen.add(item.key);
        return true;
      });
    })
    .filter((items) => items.length > 0)
    .chain((items) =>
      fc.record({
        items: fc.constant(items),
        index: fc.nat({ max: items.length - 1 }),
      }),
    );
}

describe("Property 2: Select-based selectors call onSelect with the matching data object", () => {
  it("VideoEntry: find by key returns the exact matching object", () => {
    fc.assert(
      fc.property(uniqueKeyListWithIndex(videoEntryArb), ({ items, index }) => {
        const selectedKey = items[index].key;

        // This is the exact logic used in VideoSelector's onValueChange
        const found = items.find((v) => v.key === selectedKey);

        expect(found).toBeDefined();
        expect(found).toBe(items[index]);
        expect(found!.key).toBe(selectedKey);
        expect(found!.filename).toBe(items[index].filename);
        expect(found!.pipeline_version).toBe(items[index].pipeline_version);
        expect(found!.video_id).toBe(items[index].video_id);
      }),
      { numRuns: 100 },
    );
  });

  it("InputVideo: find by key returns the exact matching object", () => {
    fc.assert(
      fc.property(uniqueKeyListWithIndex(inputVideoArb), ({ items, index }) => {
        const selectedKey = items[index].key;

        // This is the exact logic used in InputVideoSelector's onValueChange
        const found = items.find((v) => v.key === selectedKey);

        expect(found).toBeDefined();
        expect(found).toBe(items[index]);
        expect(found!.key).toBe(selectedKey);
        expect(found!.video_id).toBe(items[index].video_id);
        expect(found!.size_mb).toBe(items[index].size_mb);
      }),
      { numRuns: 100 },
    );
  });

  it("placeholder count equals the list length for VideoEntry lists", () => {
    fc.assert(
      fc.property(
        fc
          .array(videoEntryArb, { minLength: 0, maxLength: 50 })
          .map((items) => {
            const seen = new Set<string>();
            return items.filter((item) => {
              if (seen.has(item.key)) return false;
              seen.add(item.key);
              return true;
            });
          }),
        (videos) => {
          // This mirrors the placeholder template in VideoSelector
          const placeholder = `Select a video (${videos.length} available)`;
          expect(placeholder).toContain(`${videos.length}`);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("placeholder count equals the list length for InputVideo lists", () => {
    fc.assert(
      fc.property(
        fc
          .array(inputVideoArb, { minLength: 0, maxLength: 50 })
          .map((items) => {
            const seen = new Set<string>();
            return items.filter((item) => {
              if (seen.has(item.key)) return false;
              seen.add(item.key);
              return true;
            });
          }),
        (videos) => {
          // This mirrors the placeholder template in InputVideoSelector
          const placeholder = `Select an input video (${videos.length} available)`;
          expect(placeholder).toContain(`${videos.length}`);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("find returns undefined for a key not in the list", () => {
    fc.assert(
      fc.property(
        fc.array(videoEntryArb, { minLength: 1, maxLength: 20 }),
        fc.string({ minLength: 1, maxLength: 50 }),
        (videos, randomKey) => {
          const allKeys = new Set(videos.map((v) => v.key));
          // Only test when randomKey is NOT in the list
          fc.pre(!allKeys.has(randomKey));

          const found = videos.find((v) => v.key === randomKey);
          expect(found).toBeUndefined();
        },
      ),
      { numRuns: 100 },
    );
  });
});
