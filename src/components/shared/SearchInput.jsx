import { useState, useCallback, useRef, useEffect, useId, memo } from 'react';
import { Search, X } from 'lucide-react';

const SearchInput = memo(({ placeholder = 'Search...', onSearch, debounceMs = 300 }) => {
  const [value, setValue] = useState('');
  const timerRef = useRef(null);
  const inputId = useId();

  const handleChange = useCallback((e) => {
    const v = e.target.value;
    setValue(v);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => onSearch?.(v), debounceMs);
  }, [onSearch, debounceMs]);

  const handleClear = useCallback(() => {
    setValue('');
    clearTimeout(timerRef.current);
    onSearch?.('');
  }, [onSearch]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return (
    <div role="search" style={{ position: 'relative' }}>
      <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-4)' }} aria-hidden="true" />
      <label className="sr-only" htmlFor={inputId}>Search</label>
      <input
        id={inputId}
        className="input-field"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        style={{ paddingLeft: 32, paddingRight: value ? 28 : undefined }}
        aria-label={placeholder}
      />
      {value && (
        <button
          onClick={handleClear}
          aria-label="Clear search"
          style={{
            position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)',
            background: 'none', border: 'none', cursor: 'pointer', padding: 2,
            color: 'var(--text-4)', display: 'flex', alignItems: 'center',
          }}
          title="Clear search"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
});
SearchInput.displayName = "SearchInput";
export default SearchInput;
