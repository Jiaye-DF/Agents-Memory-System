import React from "react";

interface LogoProps {
  className?: string;
}

export const Logo = React.memo(function Logo({
  className = "",
}: LogoProps): React.ReactNode {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Agents Platform Logo"
    >
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path
        d="M8 22L16 10L24 22H8Z"
        className="stroke-white"
        strokeWidth="2"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="16" cy="18" r="2" className="fill-white" />
    </svg>
  );
});
