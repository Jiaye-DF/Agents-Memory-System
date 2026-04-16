"use client";

import React, { forwardRef } from "react";

interface InputProps {
  label?: string;
  error?: string;
  id?: string;
  type?: string;
  placeholder?: string;
  value?: string;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onBlur?: (e: React.FocusEvent<HTMLInputElement>) => void;
}

export const Input = React.memo(
  forwardRef<HTMLInputElement, InputProps>(function Input(
    {
      label,
      error,
      id,
      type = "text",
      placeholder,
      value,
      disabled = false,
      required = false,
      className = "",
      onChange,
      onBlur,
    }: InputProps,
    ref
  ): React.ReactNode {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="mb-1.5 block text-sm font-medium text-foreground"
          >
            {label}
            {required && <span className="ml-0.5 text-destructive">*</span>}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          type={type}
          placeholder={placeholder}
          value={value}
          disabled={disabled}
          required={required}
          onChange={onChange}
          onBlur={onBlur}
          className={`min-h-[44px] w-full rounded-xl border bg-input-bg px-3 py-2 text-sm text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 disabled:cursor-not-allowed disabled:opacity-50 ${
            error ? "border-destructive" : "border-input-border"
          } ${className}`}
        />
        {error && (
          <p className="mt-1 text-sm text-destructive">{error}</p>
        )}
      </div>
    );
  })
);
