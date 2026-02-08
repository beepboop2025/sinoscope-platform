import { useState, useCallback } from 'react';
import { storageRead, storageWrite } from '../utils/storage';
import { DEFAULT_WORKSPACES } from '../constants/workspaces';

const STORAGE_KEY = 'dragonscope_workspaces';
const ACTIVE_KEY = 'dragonscope_active_workspace';

export function useWorkspace() {
  const [workspaces, setWorkspaces] = useState(() => {
    const saved = storageRead(STORAGE_KEY);
    return saved || { ...DEFAULT_WORKSPACES };
  });

  const [activeId, setActiveId] = useState(() => {
    return storageRead(ACTIVE_KEY) || 'overview';
  });

  const activeWorkspace = workspaces[activeId] || workspaces.overview;

  const switchWorkspace = useCallback((id) => {
    setActiveId(id);
    storageWrite(ACTIVE_KEY, id);
  }, []);

  const updateLayout = useCallback((id, layout) => {
    setWorkspaces(prev => {
      const next = { ...prev, [id]: { ...prev[id], layout } };
      storageWrite(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const createWorkspace = useCallback((name) => {
    const id = name.toLowerCase().replace(/\s+/g, '_');
    setWorkspaces(prev => {
      const next = {
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

  const deleteWorkspace = useCallback((id) => {
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

  const addPanelToWorkspace = useCallback((panelId) => {
    setWorkspaces(prev => {
      const ws = prev[activeId];
      if (!ws || ws.panels.includes(panelId)) return prev;
      const maxY = ws.layout.reduce((m, l) => Math.max(m, l.y + l.h), 0);
      const next = {
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
