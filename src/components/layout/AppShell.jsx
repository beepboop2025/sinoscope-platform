import Header from './Header';
import Footer from './Footer';
import RateTicker from './RateTicker';
import WorkspaceTabs from './WorkspaceTabs';

export default function AppShell({ children, marketData, wsStatus, workspace, onOpenCommandBar }) {
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
