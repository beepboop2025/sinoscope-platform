import { useState, useCallback, useRef, useEffect, memo } from 'react';
import { Search } from 'lucide-react';

const SearchInput = memo(({ placeholder = 'Search...', onSearch, debounceMs = 300 }) => {
  const [value, setValue] = useState('');
  const timerRef = useRef(null);

  const handleChange = useCallback((e) => {
    const v = e.target.value;
    setValue(v);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => onSearch?.(v), debounceMs);
  }, [onSearch, debounceMs]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return (
    <div style={{ position: 'relative' }}>
      <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-4)' }} />
      <input
        className="input-field"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        style={{ paddingLeft: 32 }}
      />
    </div>
  );
});
SearchInput.displayName = "SearchInput";
export default SearchInput;
