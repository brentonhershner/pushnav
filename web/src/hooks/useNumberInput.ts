import { useEffect, useRef, useState } from "react";

const DEBOUNCE_MS = 600;

/**
 * Controlled number input behaviour:
 * - Spinner clicks and arrow-key steps commit immediately.
 * - Manual typing debounces by DEBOUNCE_MS before committing.
 * - Blur always flushes any pending debounce.
 * - Server-pushed value changes are reflected while the field is unfocused.
 */
export function useNumberInput(
  serverValue: number,
  onCommit: (value: number) => void,
) {
  const [localValue, setLocalValue] = useState(serverValue);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editingRef = useRef(false);

  useEffect(() => {
    if (!editingRef.current) setLocalValue(serverValue);
  }, [serverValue]);

  function commit(v: number) {
    if (!Number.isNaN(v)) onCommit(v);
  }

  const inputProps = {
    value: localValue,
    onFocus: () => { editingRef.current = true; },
    onBlur: (e: React.FocusEvent<HTMLInputElement>) => {
      editingRef.current = false;
      if (debounceRef.current) { clearTimeout(debounceRef.current); debounceRef.current = null; }
      commit(Number(e.currentTarget.value));
    },
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      const v = Number(e.currentTarget.value);
      setLocalValue(v);
      const inputType = (e.nativeEvent as InputEvent).inputType;
      const isManualEdit = inputType?.startsWith("insert") || inputType?.startsWith("delete");
      if (isManualEdit) {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => { debounceRef.current = null; commit(v); }, DEBOUNCE_MS);
      } else {
        if (debounceRef.current) { clearTimeout(debounceRef.current); debounceRef.current = null; }
        commit(v);
      }
    },
  };

  return inputProps;
}
