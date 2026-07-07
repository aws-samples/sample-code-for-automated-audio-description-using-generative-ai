import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { cn } from "@/lib/utils";

/**
 * Feature: shadcn-ui-migration, Property 1: cn() utility merges Tailwind classes with conflict resolution
 * Validates: Requirements 1.5
 *
 * For any two strings of Tailwind CSS classes where both contain a class
 * targeting the same CSS property (e.g., bg-red-500 and bg-blue-500),
 * calling cn(classesA, classesB) should return a string where the later
 * class wins and the earlier conflicting class is removed, and all
 * non-conflicting classes from both inputs are preserved.
 */

// Tailwind class groups that target the same CSS property
const conflictGroups = {
  bg: [
    "bg-red-500",
    "bg-blue-500",
    "bg-green-500",
    "bg-yellow-500",
    "bg-purple-500",
    "bg-pink-500",
  ],
  text: [
    "text-red-500",
    "text-blue-500",
    "text-green-500",
    "text-yellow-500",
    "text-purple-500",
  ],
  p: ["p-1", "p-2", "p-3", "p-4", "p-6", "p-8"],
  m: ["m-1", "m-2", "m-3", "m-4", "m-6", "m-8"],
  rounded: [
    "rounded-sm",
    "rounded-md",
    "rounded-lg",
    "rounded-xl",
    "rounded-full",
  ],
  font: [
    "font-thin",
    "font-normal",
    "font-medium",
    "font-semibold",
    "font-bold",
  ],
  textSize: [
    "text-xs",
    "text-sm",
    "text-base",
    "text-lg",
    "text-xl",
    "text-2xl",
  ],
  w: ["w-1", "w-2", "w-4", "w-8", "w-12", "w-full"],
  h: ["h-1", "h-2", "h-4", "h-8", "h-12", "h-full"],
} as const;

const conflictGroupKeys = Object.keys(
  conflictGroups,
) as (keyof typeof conflictGroups)[];

// Non-conflicting utility classes — each targets a UNIQUE CSS property
// so tailwind-merge will never remove any when combined together.
const nonConflictingClasses = [
  "flex",
  "items-center",
  "justify-between",
  "gap-2",
  "border",
  "opacity-75",
  "cursor-pointer",
  "overflow-hidden",
  "relative",
  "z-10",
  "underline",
  "uppercase",
  "shadow-md",
  "transition",
  "pointer-events-none",
];

// Arbitrary to pick a conflict group and two different classes from it
const conflictPairArb = fc
  .constantFrom(...conflictGroupKeys)
  .chain((groupKey) => {
    const group = conflictGroups[groupKey];
    return fc
      .tuple(fc.constantFrom(...group), fc.constantFrom(...group))
      .filter(([a, b]) => a !== b);
  });

// Arbitrary for a small set of non-conflicting classes
const nonConflictingSetArb = fc.subarray(nonConflictingClasses, {
  minLength: 0,
  maxLength: 5,
});

describe("Property 1: cn() utility merges Tailwind classes with conflict resolution", () => {
  it("later conflicting class wins and earlier conflicting class is removed", () => {
    fc.assert(
      fc.property(
        conflictPairArb,
        nonConflictingSetArb,
        nonConflictingSetArb,
        ([classA, classB], extraA, extraB) => {
          // classA and classB conflict (same CSS property group)
          // extraA and extraB are non-conflicting with each other and with the conflict pair
          const inputA = [classA, ...extraA].join(" ");
          const inputB = [classB, ...extraB].join(" ");

          const result = cn(inputA, inputB);
          const resultClasses = result.split(/\s+/).filter(Boolean);

          // The later conflicting class (classB) should be present
          expect(resultClasses).toContain(classB);

          // The earlier conflicting class (classA) should be removed
          expect(resultClasses).not.toContain(classA);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("all non-conflicting classes from both inputs are preserved", () => {
    fc.assert(
      fc.property(
        nonConflictingSetArb.filter((arr) => arr.length > 0),
        nonConflictingSetArb.filter((arr) => arr.length > 0),
        (setA, setB) => {
          const inputA = setA.join(" ");
          const inputB = setB.join(" ");

          const result = cn(inputA, inputB);
          const resultClasses = result.split(/\s+/).filter(Boolean);

          // All unique classes from both inputs should be in the result
          const allUnique = [...new Set([...setA, ...setB])];
          for (const cls of allUnique) {
            expect(resultClasses).toContain(cls);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it("result contains no duplicate classes", () => {
    fc.assert(
      fc.property(
        conflictPairArb,
        nonConflictingSetArb,
        ([classA, classB], extras) => {
          const input = [classA, ...extras, classB].join(" ");
          const result = cn(input);
          const resultClasses = result.split(/\s+/).filter(Boolean);

          // No class should appear more than once
          const unique = new Set(resultClasses);
          expect(resultClasses).toHaveLength(unique.size);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("returns a non-empty string when given non-empty inputs", () => {
    fc.assert(
      fc.property(fc.constantFrom(...nonConflictingClasses), (cls) => {
        const result = cn(cls);
        expect(result.length).toBeGreaterThan(0);
        expect(result.trim()).toBe(result);
      }),
      { numRuns: 100 },
    );
  });
});
