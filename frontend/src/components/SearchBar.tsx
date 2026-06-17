import { useState, useRef, useEffect } from "react";
import { CountryRisk } from "../types";

interface Props {
  countries: CountryRisk[];
  onSelect: (code: string) => void;
  isMobile: boolean;
}

function riskColor(v: number) {
  if (v >= 0.8) return "#ff4466";
  if (v >= 0.6) return "#ff9430";
  if (v >= 0.4) return "#ffd440";
  return "#aaff44";
}

export function SearchBar({ countries, onSelect, isMobile }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const results = query.length >= 1
    ? countries
        .filter((c) => c.country_name.toLowerCase().includes(query.toLowerCase()))
        .sort((a, b) => b.risk_score - a.risk_score)
        .slice(0, 6)
    : [];

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const handleSelect = (code: string) => {
    onSelect(code);
    setOpen(false);
    setQuery("");
  };

  return (
    <div style={{
      position: "absolute",
      top: isMobile ? 8 : 12,
      left: isMobile ? 12 : 50,
      zIndex: 900,
      width: open ? (isMobile ? "calc(100vw - 24px)" : 250) : 40,
      transition: "width 0.2s ease",
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        background: "rgba(8, 16, 26, 0.95)",
        backdropFilter: "blur(16px)",
        border: "1px solid rgba(0, 210, 170, 0.15)",
        borderRadius: open ? "5px 5px 0 0" : 5,
        overflow: "hidden",
        boxShadow: "0 4px 16px rgba(0,0,0,0.35)",
      }}>
        <button
          onClick={() => { setOpen((v) => !v); if (!open) setTimeout(() => inputRef.current?.focus(), 50); }}
          style={{
            background: "none", border: "none", cursor: "pointer",
            width: 40, height: 40, display: "flex", alignItems: "center", justifyContent: "center",
            color: open ? "#00d2aa" : "rgba(228,237,245,0.35)",
            flexShrink: 0, fontSize: 14, transition: "color 0.12s",
          }}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5" />
            <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
        {open && (
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search country..."
            style={{
              flex: 1, background: "none", border: "none", outline: "none",
              color: "#e4edf5", fontSize: 13, padding: "0 10px 0 0",
              caretColor: "#00d2aa",
            }}
          />
        )}
        {open && query && (
          <button onClick={() => setQuery("")} style={{ background: "none", border: "none", color: "rgba(228,237,245,0.3)", cursor: "pointer", padding: "0 10px", fontSize: 13 }}>
            ✕
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div style={{
          background: "rgba(8, 16, 26, 0.98)",
          backdropFilter: "blur(16px)",
          border: "1px solid rgba(0, 210, 170, 0.15)",
          borderTop: "1px solid rgba(228,237,245,0.04)",
          borderRadius: "0 0 5px 5px",
          overflow: "hidden",
          boxShadow: "0 8px 20px rgba(0,0,0,0.45)",
        }}>
          {results.map((c) => (
            <button
              key={c.country_code}
              onClick={() => handleSelect(c.country_code)}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                width: "100%", background: "none", border: "none",
                borderBottom: "1px solid rgba(228,237,245,0.04)", cursor: "pointer",
                padding: "9px 14px", textAlign: "left",
                transition: "background 0.1s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(0,210,170,0.05)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
            >
              <div>
                <span style={{ fontSize: 13, color: "#e4edf5", fontWeight: 500 }}>{c.country_name}</span>
                <span style={{ fontSize: 10, color: "rgba(228,237,245,0.3)", marginLeft: 6, fontFamily: "monospace" }}>{c.country_code}</span>
              </div>
              <span style={{ fontSize: 12, fontWeight: 700, color: riskColor(c.risk_score), fontFamily: "'JetBrains Mono', monospace" }}>
                {(c.risk_score * 100).toFixed(0)}%
              </span>
            </button>
          ))}
        </div>
      )}

      {open && query.length > 0 && results.length === 0 && (
        <div style={{
          background: "rgba(8,16,26,0.98)", border: "1px solid rgba(0,210,170,0.15)",
          borderTop: "1px solid rgba(228,237,245,0.04)", borderRadius: "0 0 5px 5px",
          padding: "12px 14px", fontSize: 12, color: "rgba(228,237,245,0.3)",
        }}>
          No results
        </div>
      )}
    </div>
  );
}
