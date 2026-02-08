import { memo, useState } from 'react';
import { Plus, X } from 'lucide-react';

const WorkspaceTabs = memo(({ workspaces, activeId, onSwitch, onCreate, onDelete }) => {
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState('');

  const handleCreate = () => {
    if (newName.trim()) {
      onCreate(newName.trim());
      setNewName('');
      setShowNew(false);
    }
  };

  return (
    <div className="workspace-tabs" role="tablist" aria-label="Workspaces">
      {Object.values(workspaces).map(ws => (
        <button
          key={ws.id}
          className={`workspace-tab ${activeId === ws.id ? 'active' : ''}`}
          onClick={() => onSwitch(ws.id)}
          role="tab"
          aria-selected={activeId === ws.id}
          tabIndex={activeId === ws.id ? 0 : -1}
        >
          {ws.name}
          {ws.id !== 'overview' && activeId === ws.id && (
            <X
              size={10}
              style={{ marginLeft: 4, opacity: 0.5 }}
              onClick={(e) => { e.stopPropagation(); onDelete(ws.id); }}
              aria-label={`Close ${ws.name} workspace`}
            />
          )}
        </button>
      ))}
      {showNew ? (
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <input
            className="input-field"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            placeholder="Name..."
            style={{ width: 100, padding: '2px 6px', fontSize: 11 }}
            aria-label="New workspace name"
            autoFocus
          />
          <button className="btn-ghost" onClick={handleCreate} style={{ padding: '2px 6px' }} aria-label="Create workspace">OK</button>
        </div>
      ) : (
        <button className="workspace-tab" onClick={() => setShowNew(true)} aria-label="Add new workspace">
          <Plus size={12} aria-hidden="true" />
        </button>
      )}
    </div>
  );
});
WorkspaceTabs.displayName = "WorkspaceTabs";
export default WorkspaceTabs;
