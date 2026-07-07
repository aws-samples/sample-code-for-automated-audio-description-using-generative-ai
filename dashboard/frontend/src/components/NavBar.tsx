import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Page = "viewer" | "trigger" | "cost";

interface NavBarProps {
  activePage: Page;
  onNavigate: (page: Page) => void;
}

const tabs: { page: Page; label: string }[] = [
  { page: "trigger", label: "Process" },
  { page: "viewer", label: "Viewer" },
  { page: "cost", label: "Cost Estimation" },
];

function NavBar({ activePage, onNavigate }: NavBarProps) {
  return (
    <nav aria-label="Dashboard navigation">
      <Tabs value={activePage} onValueChange={(v) => onNavigate(v as Page)}>
        <TabsList className="bg-[var(--surface-container-low)] px-6 gap-0 rounded-none w-full justify-start h-auto">
          {tabs.map(({ page, label }) => (
            <TabsTrigger
              key={page}
              value={page}
              className="rounded-none border-b-2 border-transparent px-5 py-2.5 text-sm font-medium text-[var(--on-surface-muted)] transition-colors hover:text-[var(--on-surface)] focus-visible:ring-0 focus-visible:ring-offset-0 data-[state=active]:border-b-2 data-[state=active]:border-[var(--primary)] data-[state=active]:text-[var(--on-surface)] data-[state=active]:shadow-none data-[state=active]:bg-transparent"
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </nav>
  );
}

export default NavBar;
