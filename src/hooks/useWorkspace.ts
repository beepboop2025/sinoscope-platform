import { useState, useCallback } from 'react';
import { storageRead, storageWrite } from '../utils/storage';
import { DEFAULT_WORKSPACES } from '../constants/workspaces';
import type { LayoutItem } from '../types';

interface WorkspaceData {
  id: string;
  name: string;
  layout: LayoutItem[];
  panels: string[];
}

type WorkspacesMap = Record<string, WorkspaceData>;

interface UseWorkspaceReturn {
  workspaces: WorkspacesMap;
  activeId: string;
  activeWorkspace: WorkspaceData;
  switchWorkspace: (id: string) => void;
  updateLayout: (id: string, layout: LayoutItem[]) => void;
  createWorkspace: (name: string) => void;
  deleteWorkspace: (id: string) => void;
  addPanelToWorkspace: (panelId: string) => void;
}

const STORAGE_KEY = 'dragonscope_workspaces';
const ACTIVE_KEY = 'dragonscope_active_workspace';

export function useWorkspace(): UseWorkspaceReturn {
  const [workspaces, setWorkspaces] = useState<WorkspacesMap>(() => {
    const saved = storageRead<WorkspacesMap | null>(STORAGE_KEY);
    return saved || { ...DEFAULT_WORKSPACES } as WorkspacesMap;
  });

  const [activeId, setActiveId] = useState<string>(() => {
    return storageRead<string>(ACTIVE_KEY) || 'overview';
  });

  const activeWorkspace = (workspaces[activeId] || workspaces.overview) as WorkspaceData;

  const switchWorkspace = useCallback((id: string): void => {
    setActiveId(id);
    storageWrite(ACTIVE_KEY, id);
  }, []);

  const updateLayout = useCallback((id: string, layout: LayoutItem[]): void => {
    setWorkspaces(prev => {
      const next = { ...prev, [id]: { ...prev[id], layout } };
      storageWrite(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const createWorkspace = useCallback((name: string): void => {
    const id = name.toLowerCase().replace(/\s+/g, '_');
    setWorkspaces(prev => {
      const next: WorkspacesMap = {
        ...prev,
        [id]: {
          id,
          name,
          layout: [{ i: 'forex', x: 0, y: 0, w: 6, h: 4 }, { i: 'crypto', x: 6, y: 0, w: 6, h: 4 }],
          panels: ['forex', 'crypto'],
        },
      };
      storageWrite(STORAGE_KEY, next);
      return next;
    });
    setActiveId(id);
    storageWrite(ACTIVE_KEY, id);
  }, []);

  const deleteWorkspace = useCallback((id: string): void => {
    if (id === 'overview') return;
    setWorkspaces(prev => {
      const next = { ...prev };
      delete next[id];
      storageWrite(STORAGE_KEY, next);
      return next;
    });
    if (activeId === id) {
      setActiveId('overview');
      storageWrite(ACTIVE_KEY, 'overview');
    }
  }, [activeId]);

  const addPanelToWorkspace = useCallback((panelId: string): void => {
    setWorkspaces(prev => {
      const ws = prev[activeId];
      if (!ws || ws.panels.includes(panelId)) return prev;
      const maxY = ws.layout.reduce((m: number, l: LayoutItem) => Math.max(m, l.y + l.h), 0);
      const next: WorkspacesMap = {
        ...prev,
        [activeId]: {
          ...ws,
          layout: [...ws.layout, { i: panelId, x: 0, y: maxY, w: 6, h: 4 }],
          panels: [...ws.panels, panelId],
        },
      };
      storageWrite(STORAGE_KEY, next);
      return next;
    });
  }, [activeId]);

  return {
    workspaces,
    activeId,
    activeWorkspace,
    switchWorkspace,
    updateLayout,
    createWorkspace,
    deleteWorkspace,
    addPanelToWorkspace,
  };
}
