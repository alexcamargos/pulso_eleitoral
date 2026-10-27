"use client";

import React from "react";
import { ShieldCheck, Info, ExternalLink } from "lucide-react";
import { MetadataPayload } from "../types/audit";

interface HeaderProps {
  metadata: MetadataPayload | null;
  ano: number;
  turno: number;
  onSelectElection: (ano: number, turno: number) => void;
  onOpenMethodology: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  metadata,
  ano,
  turno,
  onSelectElection,
  onOpenMethodology,
}) => {
  return (
    <header className="bg-[#181B20] text-[#E2E8F0] border-b border-[#282D37] sticky top-0 z-40 backdrop-blur-md bg-opacity-95">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-3">
        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[#38BDF8]/15 border border-[#38BDF8]/30 rounded-lg text-[#38BDF8]" aria-hidden="true">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg sm:text-xl font-bold tracking-tight text-[#F8FAFC]">
                  Pulso Eleitoral
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#38BDF8]/15 text-[#38BDF8] border border-[#38BDF8]/30">
                  TSE Audit
                </span>
              </div>
              <p className="text-xs text-[#94A3B8]">
                Auditoria de Urnas & Análise da Extensão de Votação
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Seletor de Pleito */}
            <div className="flex items-center gap-2 bg-[#121417] px-3 py-1.5 rounded-lg border border-[#282D37]">
              <label htmlFor="election-select" className="text-xs font-semibold text-[#94A3B8] uppercase tracking-wider">
                Pleito:
              </label>
              <select
                id="election-select"
                value={`${ano}-${turno}`}
                onChange={(e) => {
                  const [newAno, newTurno] = e.target.value.split("-").map(Number);
                  onSelectElection(newAno, newTurno);
                }}
                className="bg-transparent text-[#F8FAFC] text-xs font-medium focus:ring-0 outline-none cursor-pointer"
              >
                <option value="2026-2" className="bg-[#181B20] text-[#F8FAFC]">
                  Eleições 2026 — 2º Turno (Presidencial)
                </option>
                <option value="2022-1" className="bg-[#181B20] text-[#F8FAFC]">
                  Eleições 2022 — 1º Turno (Presidencial)
                </option>
                <option value="2022-2" className="bg-[#181B20] text-[#F8FAFC]">
                  Eleições 2022 — 2º Turno (Presidencial)
                </option>
              </select>
            </div>

            {/* Botão Metodologia */}
            <button
              onClick={onOpenMethodology}
              className="flex items-center gap-1.5 bg-[#242933] hover:bg-[#2e3442] text-[#38BDF8] border border-[#282D37] hover:border-[#38BDF8]/50 text-xs font-semibold px-3 py-1.5 rounded-lg transition-all"
              aria-label="Abrir notas de transparência metodológica e hash de auditoria"
            >
              <Info className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Metodologia</span>
            </button>

            {/* Link TSE */}
            <a
              href="https://resultados.tse.jus.br"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:flex items-center gap-1 text-xs text-[#94A3B8] hover:text-[#F8FAFC] transition-colors"
            >
              <span>Portal TSE</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {/* Linha de status e integridade do banco */}
        {metadata && (
          <div className="mt-2.5 pt-2 border-t border-[#282D37] flex flex-wrap items-center justify-between text-[11px] text-[#94A3B8] gap-2">
            <div className="flex items-center gap-3">
              <span>
                Pipeline: <strong className="text-[#CBD5E1]">v{metadata.pipeline_version}</strong>
              </span>
              <span>&bull;</span>
              <span>
                Fuso: <strong className="text-[#CBD5E1]">{metadata.cutoff_mode}</strong>
              </span>
              <span>&bull;</span>
              <span>
                Pleito TSE: <strong className="text-[#CBD5E1]">#{metadata.pleito_id}</strong>
              </span>
            </div>
            <div className="flex items-center gap-1.5 font-mono text-[10.5px]">
              <span className="text-[#64748B]">SHA-256:</span>
              <span className="bg-[#121417] px-2 py-0.5 rounded border border-[#282D37] text-[#38BDF8] truncate max-w-[240px] sm:max-w-[320px]" title={metadata.duckdb_sha256}>
                {metadata.duckdb_sha256}
              </span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
