"use client";

import React from "react";
import { ShieldCheck, Info, FileText } from "lucide-react";
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
    <header className="bg-slate-900 text-white shadow-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600 rounded-lg text-white" aria-hidden="true">
              <ShieldCheck className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight">
                Pulso Eleitoral
              </h1>
              <p className="text-xs sm:text-sm text-slate-300">
                Auditoria Técnica e Reproduzível de Logs de Urna TSE
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Seletor de Pleito */}
            <div className="flex items-center gap-2 bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700">
              <label htmlFor="election-select" className="text-xs font-medium text-slate-300">
                Pleito:
              </label>
              <select
                id="election-select"
                value={`${ano}-${turno}`}
                onChange={(e) => {
                  const [newAno, newTurno] = e.target.value.split("-").map(Number);
                  onSelectElection(newAno, newTurno);
                }}
                className="bg-slate-900 text-white text-xs sm:text-sm rounded border border-slate-700 px-2 py-1 focus:ring-2 focus:ring-blue-500 outline-none"
              >
                <option value="2022-1">Eleições 2022 — 1º Turno</option>
                <option value="2022-2">Eleições 2022 — 2º Turno</option>
              </select>
            </div>

            {/* Botão Metodologia */}
            <button
              onClick={onOpenMethodology}
              className="flex items-center gap-1.5 bg-blue-700 hover:bg-blue-600 text-white text-xs sm:text-sm px-3 py-1.5 rounded-lg transition-colors focus:ring-2 focus:ring-blue-400"
              aria-label="Abrir notas de transparência metodológica e hash de auditoria"
            >
              <Info className="w-4 h-4" aria-hidden="true" />
              <span>Metodologia & Integridade</span>
            </button>
          </div>
        </div>

        {/* Linha de status e integridade do banco */}
        {metadata && (
          <div className="mt-3 pt-3 border-t border-slate-800 flex flex-wrap items-center justify-between text-xs text-slate-400 gap-2">
            <div className="flex items-center gap-4">
              <span>
                Pipeline: <strong className="text-slate-200">v{metadata.pipeline_version}</strong>
              </span>
              <span>
                Fuso: <strong className="text-slate-200">{metadata.cutoff_mode}</strong>
              </span>
            </div>
            <div className="flex items-center gap-2 font-mono text-[11px] truncate max-w-full">
              <span className="text-slate-400">DuckDB SHA-256:</span>
              <span className="bg-slate-800 px-2 py-0.5 rounded text-blue-300 truncate" title={metadata.duckdb_sha256}>
                {metadata.duckdb_sha256}
              </span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
