import { memo, useState, useEffect, useCallback } from 'react';
import { Key, Plus, Trash2, Eye, EyeOff, Check } from 'lucide-react';
import { storageRead, storageWrite } from '../../utils/storage';

const PROVIDERS = [
  { id: 'finnhub', name: 'Finnhub', envKey: 'VITE_FINNHUB_API_KEY' },
  { id: 'fmp', name: 'FMP', envKey: 'VITE_FMP_API_KEY' },
  { id: 'alphavantage', name: 'Alpha Vantage', envKey: 'VITE_ALPHA_VANTAGE_API_KEY' },
  { id: 'newsdata', name: 'NewsData.io', envKey: 'VITE_NEWSDATA_API_KEY' },
  { id: 'newsapiorg', name: 'NewsAPI.org', envKey: 'VITE_NEWSAPI_ORG_KEY' },
  { id: 'worldnews', name: 'WorldNewsAPI', envKey: 'VITE_WORLD_NEWS_API_KEY' },
  { id: 'gnews', name: 'GNews', envKey: 'VITE_GNEWS_API_KEY' },
];

const STORAGE_KEY = 'dragonscope_user_api_keys';

const ApiKeyManager = memo(({ isOpen, onClose }) => {
  const [keys, setKeys] = useState(() => storageRead(STORAGE_KEY, {}));
  const [editing, setEditing] = useState(null);
  const [inputVal, setInputVal] = useState('');
  const [showKey, setShowKey] = useState({});
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    storageWrite(STORAGE_KEY, keys);
  }, [keys]);

  const handleSave = useCallback((providerId) => {
    if (!inputVal.trim()) return;
    setKeys(prev => ({ ...prev, [providerId]: inputVal.trim() }));
    setEditing(null);
    setInputVal('');
    setSaved(providerId);
    setTimeout(() => setSaved(null), 1500);
  }, [inputVal]);

  const handleDelete = useCallback((providerId) => {
    setKeys(prev => {
      const next = { ...prev };
      delete next[providerId];
      return next;
    });
  }, []);

  if (!isOpen) return null;

  const inputStyle = {
    background: 'var(--bg-0)', border: '1px solid var(--border-2)', borderRadius: 4,
    color: 'var(--text-1)', fontSize: 10, padding: '4px 8px', fontFamily: 'var(--font-mono)',
    outline: 'none', flex: 1,
  };

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.6)', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: 'var(--bg-1)', border: '1px solid var(--border-2)',
        borderRadius: 10, padding: 20, width: 440, maxWidth: '90vw', maxHeight: '80vh', overflow: 'auto',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Key size={16} color="var(--amber)" />
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>API Keys</span>
          </div>
          <button onClick={onClose} className="btn-ghost" style={{ padding: 4, fontSize: 11 }}>Esc</button>
        </div>

        <div style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 12 }}>
          Manage your API keys for data providers. Keys are stored locally in your browser.
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {PROVIDERS.map(p => {
            const hasKey = !!keys[p.id];
            const envHasKey = !!import.meta.env[p.envKey];
            const isEditing = editing === p.id;

            return (
              <div key={p.id} style={{
                padding: '8px 10px', background: 'var(--bg-2)', borderRadius: 6,
                border: '1px solid var(--border-1)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-1)' }}>{p.name}</span>
                  <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                    {saved === p.id && <Check size={12} color="var(--green)" />}
                    {hasKey && (
                      <>
                        <button className="btn-ghost" onClick={() => setShowKey(prev => ({ ...prev, [p.id]: !prev[p.id] }))} style={{ padding: '1px 4px' }}>
                          {showKey[p.id] ? <EyeOff size={10} /> : <Eye size={10} />}
                        </button>
                        <button className="btn-ghost" onClick={() => handleDelete(p.id)} style={{ padding: '1px 4px', color: 'var(--text-4)' }}>
                          <Trash2 size={10} />
                        </button>
                      </>
                    )}
                    {!isEditing && (
                      <button className="btn-ghost" onClick={() => { setEditing(p.id); setInputVal(keys[p.id] || ''); }} style={{ padding: '1px 6px', fontSize: 9 }}>
                        <Plus size={10} /> {hasKey ? 'Edit' : 'Add'}
                      </button>
                    )}
                  </div>
                </div>

                {hasKey && !isEditing && (
                  <div style={{ fontSize: 9, color: 'var(--text-4)', marginTop: 3, fontFamily: 'var(--font-mono)' }}>
                    {showKey[p.id] ? keys[p.id] : '••••••••••••' + (keys[p.id]?.slice(-4) || '')}
                  </div>
                )}

                {envHasKey && !hasKey && (
                  <div style={{ fontSize: 9, color: 'var(--green)', marginTop: 3 }}>
                    Configured via .env
                  </div>
                )}

                {isEditing && (
                  <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                    <input
                      autoFocus value={inputVal} onChange={e => setInputVal(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') handleSave(p.id); if (e.key === 'Escape') setEditing(null); }}
                      placeholder={`Enter ${p.name} API key...`}
                      type="password"
                      style={inputStyle}
                    />
                    <button className="btn-primary" onClick={() => handleSave(p.id)} style={{ padding: '3px 8px', fontSize: 9 }}>Save</button>
                    <button className="btn-ghost" onClick={() => setEditing(null)} style={{ padding: '3px 6px', fontSize: 9 }}>Cancel</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
});
ApiKeyManager.displayName = 'ApiKeyManager';
export default ApiKeyManager;
