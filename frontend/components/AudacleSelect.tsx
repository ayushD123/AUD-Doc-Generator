"use client";

import {
  KeyboardEvent,
  ReactNode,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

export type AudacleSelectOption = {
  value: string;
  label: string;
  description?: string;
  icon?: ReactNode;
};

type AudacleSelectProps = {
  label?: string;
  value: string;
  options: AudacleSelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
  compact?: boolean;
  leadingIcon?: ReactNode;
};

function ChevronIcon() {
  return (
    <svg className="audacle-select-chevron" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="audacle-select-check" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m5 12.5 4.2 4.2L19 7" />
    </svg>
  );
}

export function AudacleSelect({
  label,
  value,
  options,
  onChange,
  disabled = false,
  placeholder = "Select an option",
  className,
  ariaLabel,
  compact = false,
  leadingIcon,
}: AudacleSelectProps) {
  const listboxId = useId();
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [isOpen, setIsOpen] = useState(false);
  const selectedIndex = options.findIndex((option) => option.value === value);
  const selectedOption = selectedIndex >= 0 ? options[selectedIndex] : null;
  const selectedLeadingIcon = leadingIcon ?? selectedOption?.icon;
  const [highlightedIndex, setHighlightedIndex] = useState(
    selectedIndex >= 0 ? selectedIndex : 0,
  );

  const activeOptionId = useMemo(
    () => `${listboxId}-option-${highlightedIndex}`,
    [highlightedIndex, listboxId],
  );

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      optionRefs.current[highlightedIndex]?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightedIndex, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      setHighlightedIndex(selectedIndex >= 0 ? selectedIndex : 0);
    }
  }, [isOpen, selectedIndex]);

  function moveHighlight(direction: 1 | -1) {
    if (options.length === 0) {
      return;
    }

    setHighlightedIndex((current) => (current + direction + options.length) % options.length);
  }

  function selectOption(option: AudacleSelectOption) {
    onChange(option.value);
    setIsOpen(false);
  }

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "Escape") {
      setIsOpen(false);
      return;
    }

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setIsOpen(true);
      moveHighlight(event.key === "ArrowDown" ? 1 : -1);
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();

      if (isOpen && options[highlightedIndex]) {
        selectOption(options[highlightedIndex]);
      } else {
        setIsOpen(true);
      }
    }
  }

  return (
    <div
      ref={wrapperRef}
      className={[
        "audacle-select",
        compact ? "audacle-select-compact" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {label ? <span className="audacle-select-label">{label}</span> : null}
      <button
        type="button"
        className="audacle-select-trigger"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        aria-activedescendant={isOpen ? activeOptionId : undefined}
        aria-label={ariaLabel ?? label}
        disabled={disabled}
        onClick={() => setIsOpen((current) => !current)}
        onKeyDown={handleTriggerKeyDown}
      >
        {selectedLeadingIcon ? (
          <span className="audacle-select-leading-icon">{selectedLeadingIcon}</span>
        ) : null}
        <span className={selectedOption ? "audacle-select-value" : "audacle-select-placeholder"}>
          {selectedOption?.label ?? placeholder}
        </span>
        <ChevronIcon />
      </button>

      {isOpen ? (
        <div id={listboxId} className="audacle-select-menu" role="listbox" aria-label={ariaLabel ?? label}>
          {options.map((option, index) => {
            const isSelected = option.value === value;
            const isHighlighted = index === highlightedIndex;

            return (
              <button
                key={option.value}
                id={`${listboxId}-option-${index}`}
                ref={(node) => {
                  optionRefs.current[index] = node;
                }}
                type="button"
                className={[
                  "audacle-select-option",
                  isSelected ? "audacle-select-option-selected" : "",
                  isHighlighted ? "audacle-select-option-highlighted" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setHighlightedIndex(index)}
                onClick={() => selectOption(option)}
              >
                {option.icon ? <span className="audacle-select-option-icon">{option.icon}</span> : null}
                <span className="audacle-select-option-copy">
                  <span>{option.label}</span>
                  {option.description ? <small>{option.description}</small> : null}
                </span>
                {isSelected ? <CheckIcon /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
