import type { ServiceCostItem } from "../types";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

interface CostBreakdownTableProps {
  items: ServiceCostItem[];
  totalCost: number;
}

export function formatCost(value: number): string {
  return `${value.toFixed(6)}`;
}

export function groupByService(items: ServiceCostItem[]): ServiceCostItem[] {
  const groups = new Map<string, ServiceCostItem[]>();
  for (const item of items) {
    const existing = groups.get(item.service);
    if (existing) {
      existing.push(item);
    } else {
      groups.set(item.service, [item]);
    }
  }
  return Array.from(groups.values()).flat();
}

function CostBreakdownTable({ items, totalCost }: CostBreakdownTableProps) {
  const grouped = groupByService(items);

  return (
    <div className="flex flex-col gap-3">
      <Table className="text-[13px]">
        <TableHeader>
          <TableRow className="bg-[var(--surface-container-high)] hover:bg-[var(--surface-container-high)]">
            <TableHead className="px-2.5 py-2 text-[12px] font-semibold uppercase text-[var(--on-surface-muted)]">
              Service
            </TableHead>
            <TableHead className="px-2.5 py-2 text-[12px] font-semibold uppercase text-[var(--on-surface-muted)]">
              Description
            </TableHead>
            <TableHead className="px-2.5 py-2 text-[12px] font-semibold uppercase text-[var(--on-surface-muted)]">
              Usage
            </TableHead>
            <TableHead className="px-2.5 py-2 text-right text-[12px] font-semibold uppercase text-[var(--on-surface-muted)]">
              Cost (USD)
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {grouped.map((item, idx) => (
            <TableRow
              key={idx}
              className="even:bg-[var(--surface)] odd:bg-[var(--surface-container-low)] hover:bg-[var(--surface-container-highest)]"
            >
              <TableCell className="px-2.5 py-1.5">{item.service}</TableCell>
              <TableCell className="px-2.5 py-1.5">
                {item.description}
              </TableCell>
              <TableCell className="px-2.5 py-1.5">{item.usage}</TableCell>
              <TableCell className="px-2.5 py-1.5 text-right font-mono text-[var(--on-surface)]">
                {formatCost(item.cost_usd)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex justify-between px-2.5 py-3 bg-[var(--surface-container-high)] rounded-[var(--radius-md)] font-bold text-[15px] text-[var(--on-surface)]">
        <span>Total Cost</span>
        <span className="font-mono text-[var(--primary)]">
          {formatCost(totalCost)}
        </span>
      </div>
    </div>
  );
}

export default CostBreakdownTable;
