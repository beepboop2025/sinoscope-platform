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
    <div className="workspace-tabs">
      {Object.values(workspaces).map(ws => (
        <button
          key={ws.id}
          className={`workspace-tab ${activeId === ws.id ? 'active' : ''}`}
          onClick={() => onSwitch(ws.id)}
        >
          {ws.name}
          {ws.id !== 'overview' && activeId === ws.id && (
            <X
              size={10}
              style={{ marginLeft: 4, opacity: 0.5 }}
              onClick={(e) => { e.stopPropagation(); onDelete(ws.id); }}
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
            autoFocus
          />
          <button className="btn-ghost" onClick={handleCreate} style={{ padding: '2px 6px' }}>OK</button>
        </div>
      ) : (
        <button className="workspace-tab" onClick={() => setShowNew(true)}>
          <Plus size={12} />
        </button>
      )}
    </div>
  );
});
WorkspaceTabs.displayName = "WorkspaceTabs";
export default WorkspaceTabs;
