import type { ReactNode } from 'react';
import Header from './Header';
import Footer from './Footer';
import RateTicker from './RateTicker';
import WorkspaceTabs from './WorkspaceTabs';
import type { MarketTick, Workspace } from '../../types';

interface MarketData {
  forex: Record<string, MarketTick>;
  crypto: Record<string, MarketTick>;
  stocks: Record<string, MarketTick>;
  lastUpdate: Record<string, number>;
}

interface WorkspaceController {
  workspaces: Record<string, Workspace>;
  activeId: string;
  switchWorkspace: (id: string) => void;
  createWorkspace: (name: string) => void;
  deleteWorkspace: (id: string) => void;
}

interface AppShellProps {
  children: ReactNode;
  marketData: MarketData | null;
  wsStatus: string;
  workspace: WorkspaceController | null;
  onOpenCommandBar: () => void;
}

export default function AppShell({ children, marketData, wsStatus, workspace, onOpenCommandBar }: AppShellProps): React.JSX.Element {
  return (
    <div className="app-shell">
      <header role="banner">
        <Header wsStatus={wsStatus} onOpenCommandBar={onOpenCommandBar} />
        <RateTicker
          forex={marketData?.forex}
          crypto={marketData?.crypto}
          stocks={marketData?.stocks}
        />
        {workspace && (
          <WorkspaceTabs
            workspaces={workspace.workspaces}
            activeId={workspace.activeId}
            onSwitch={workspace.switchWorkspace}
            onCreate={workspace.createWorkspace}
            onDelete={workspace.deleteWorkspace}
          />
        )}
      </header>
      <main role="main" className="app-body">
        {children}
      </main>
      <footer role="contentinfo">
        <Footer
          lastUpdate={marketData?.lastUpdate?.forex || marketData?.lastUpdate?.crypto}
          wsStatus={wsStatus}
        />
      </footer>
    </div>
  );
}
