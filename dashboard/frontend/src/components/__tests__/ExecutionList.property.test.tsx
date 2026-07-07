import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import * as fc from "fast-check";
import ExecutionList from "../ExecutionList";
import type { ExecutionListItem } from "../../types";

/**
 * Feature: shadcn-ui-migration, Property 7: ExecutionList preserves ARIA listbox semantics
 * Validates: Requirements 10.4
 *
 * For any array of ExecutionListItem objects and any selectedArn (string or null),
 * each rendered list item should have role="option", tabIndex=0, and aria-selected
 * set to "true" only for the item whose execution_arn matches selectedArn.
 */
describe("Property 7: ExecutionList preserves ARIA listbox semantics", () => {
  // Use fc.integer mapped to timestamps to avoid invalid dates during shrinking
  const safeISODateArb = fc
    .integer({ min: 0, max: 4102444800000 }) // 1970-01-01 to 2100-01-01
    .map((ts) => new Date(ts).toISOString());

  const executionListItemArb: fc.Arbitrary<ExecutionListItem> = fc.record({
    execution_arn: fc.string({ minLength: 1, maxLength: 80 }),
    name: fc.string({ minLength: 1, maxLength: 50 }),
    status: fc.constantFrom(
      "RUNNING",
      "SUCCEEDED",
      "FAILED",
      "TIMED_OUT",
      "ABORTED",
    ),
    start_time: safeISODateArb,
    pipeline_version: fc.constantFrom("v1", "v2", "v3"),
  });

  // Generate a non-empty list with unique execution_arns
  const uniqueExecutionListArb = fc
    .array(executionListItemArb, { minLength: 1, maxLength: 10 })
    .map((items) => {
      const seen = new Set<string>();
      return items.filter((item) => {
        if (seen.has(item.execution_arn)) return false;
        seen.add(item.execution_arn);
        return true;
      });
    })
    .filter((items) => items.length > 0);

  it("each list item has role='option', tabIndex=0, and aria-selected true only for the selected item", () => {
    fc.assert(
      fc.property(
        uniqueExecutionListArb,
        fc.boolean(),
        (executions, selectOne) => {
          // Either select one of the items or use null
          const selectedArn = selectOne ? executions[0].execution_arn : null;
          const onSelect = vi.fn();

          const { container } = render(
            <ExecutionList
              executions={executions}
              selectedArn={selectedArn}
              onSelect={onSelect}
            />,
          );

          const listbox = container.querySelector('[role="listbox"]');
          expect(listbox).not.toBeNull();

          const options = container.querySelectorAll('[role="option"]');
          expect(options.length).toBe(executions.length);

          options.forEach((option, index) => {
            expect(option.getAttribute("tabindex")).toBe("0");

            const isSelected =
              selectedArn !== null &&
              executions[index].execution_arn === selectedArn;
            expect(option.getAttribute("aria-selected")).toBe(
              String(isSelected),
            );
          });

          container.remove();
        },
      ),
      { numRuns: 100 },
    );
  });
});

/**
 * Feature: shadcn-ui-migration, Property 8: ExecutionList keyboard and click handlers invoke onSelect
 * Validates: Requirements 10.5
 *
 * For any ExecutionListItem in the list, clicking the item or pressing Enter/Space
 * while focused should call onSelect with that ExecutionListItem object.
 */
describe("Property 8: ExecutionList keyboard and click handlers invoke onSelect", () => {
  // Use fc.integer mapped to timestamps to avoid invalid dates during shrinking
  const safeISODateArb = fc
    .integer({ min: 0, max: 4102444800000 }) // 1970-01-01 to 2100-01-01
    .map((ts) => new Date(ts).toISOString());

  const executionListItemArb: fc.Arbitrary<ExecutionListItem> = fc.record({
    execution_arn: fc.string({ minLength: 1, maxLength: 80 }),
    name: fc.string({ minLength: 1, maxLength: 50 }),
    status: fc.constantFrom(
      "RUNNING",
      "SUCCEEDED",
      "FAILED",
      "TIMED_OUT",
      "ABORTED",
    ),
    start_time: safeISODateArb,
    pipeline_version: fc.constantFrom("v1", "v2", "v3"),
  });

  // Generate a non-empty list with unique execution_arns
  const uniqueExecutionListArb = fc
    .array(executionListItemArb, { minLength: 1, maxLength: 10 })
    .map((items) => {
      const seen = new Set<string>();
      return items.filter((item) => {
        if (seen.has(item.execution_arn)) return false;
        seen.add(item.execution_arn);
        return true;
      });
    })
    .filter((items) => items.length > 0);

  it("clicking any list item calls onSelect with the corresponding ExecutionListItem", () => {
    fc.assert(
      fc.property(uniqueExecutionListArb, fc.nat(), (executions, indexSeed) => {
        const targetIndex = indexSeed % executions.length;
        const onSelect = vi.fn();

        const { container } = render(
          <ExecutionList
            executions={executions}
            selectedArn={null}
            onSelect={onSelect}
          />,
        );

        const options = container.querySelectorAll('[role="option"]');
        expect(options.length).toBe(executions.length);

        // Click the target item
        (options[targetIndex] as HTMLElement).click();

        expect(onSelect).toHaveBeenCalledTimes(1);
        expect(onSelect).toHaveBeenCalledWith(executions[targetIndex]);

        container.remove();
      }),
      { numRuns: 100 },
    );
  });

  it("pressing Enter on any list item calls onSelect with the corresponding ExecutionListItem", () => {
    fc.assert(
      fc.property(uniqueExecutionListArb, fc.nat(), (executions, indexSeed) => {
        const targetIndex = indexSeed % executions.length;
        const onSelect = vi.fn();

        const { container } = render(
          <ExecutionList
            executions={executions}
            selectedArn={null}
            onSelect={onSelect}
          />,
        );

        const options = container.querySelectorAll('[role="option"]');
        const target = options[targetIndex] as HTMLElement;

        // Simulate Enter keydown
        target.dispatchEvent(
          new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
        );

        expect(onSelect).toHaveBeenCalledTimes(1);
        expect(onSelect).toHaveBeenCalledWith(executions[targetIndex]);

        container.remove();
      }),
      { numRuns: 100 },
    );
  });

  it("pressing Space on any list item calls onSelect with the corresponding ExecutionListItem", () => {
    fc.assert(
      fc.property(uniqueExecutionListArb, fc.nat(), (executions, indexSeed) => {
        const targetIndex = indexSeed % executions.length;
        const onSelect = vi.fn();

        const { container } = render(
          <ExecutionList
            executions={executions}
            selectedArn={null}
            onSelect={onSelect}
          />,
        );

        const options = container.querySelectorAll('[role="option"]');
        const target = options[targetIndex] as HTMLElement;

        // Simulate Space keydown
        target.dispatchEvent(
          new KeyboardEvent("keydown", { key: " ", bubbles: true }),
        );

        expect(onSelect).toHaveBeenCalledTimes(1);
        expect(onSelect).toHaveBeenCalledWith(executions[targetIndex]);

        container.remove();
      }),
      { numRuns: 100 },
    );
  });
});
