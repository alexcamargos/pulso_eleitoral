"use client";

import React, { useState, useMemo } from "react";
import { Search, MapPin, X, Building } from "lucide-react";
import { MunicipalitiesPayload, MunicipalitySummaryItem } from "../types/audit";
import { formatNumber, formatPercent } from "../lib/api";

interface MunicipalDrilldownProps {
  data: MunicipalitiesPayload | null;
  uf: string | null;
  loading: boolean;
  onClearUf: () => void;
}

export const MunicipalDrilldown: React.FC<MunicipalDrilldownProps> = ({
  data,
  uf,
  loading,
  onClearUf,
}) => {
  const [searchTerm, setSearchTerm] = useState<string>("");

  const municipalities = useMemo(() => {
    if (!data?.municipalities) return [];
    return data.municipalities.filter((m) =>
      m.municipio_nome.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [data, searchTerm]);

  if (!uf) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mt-6">
      <div className="p-4 bg-slate-900 text-white flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MapPin className="w-5 h-5 text-blue-400" aria-hidden="true" />
          <h2 className="text-base font-bold">
            Detalhamento Municipal — Unidade Federativa: {uf}
          </h2>
          <span className="text-xs text-slate-300">
            ({data?.municipalities?.length || 0} municípios)
          </span>
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <label htmlFor="municipio-search" className="sr-only">
              Filtrar município
            </label>
            <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" aria-hidden="true" />
            <input
              id="municipio-search"
              type="text"
              placeholder="Buscar município..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1 text-xs bg-slate-800 text-white border border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-400 outline-none"
            />
          </div>
          <button
            onClick={onClearUf}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            aria-label="Fechar detalhamento municipal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="p-8 text-center text-slate-500 animate-pulse">
          Carregando municípios da UF {uf}...
        </div>
      ) : municipalities.length === 0 ? (
        <div className="p-8 text-center text-slate-500">
          Nenhum município encontrado para a busca especificada.
        </div>
      ) : (
        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-xs text-left text-slate-700">
            <thead className="bg-slate-100 text-slate-700 uppercase font-semibold sticky top-0 border-b border-slate-200">
              <tr>
                <th scope="col" className="px-4 py-2.5">
                  Município
                </th>
                <th scope="col" className="px-3 py-2.5 text-center">
                  Cód. TSE
                </th>
                <th scope="col" className="px-3 py-2.5 text-right">
                  Seções
                </th>
                <th scope="col" className="px-3 py-2.5 text-right">
                  Total Votos
                </th>
                <th scope="col" className="px-3 py-2.5 text-right">
                  Votos Pós-17h (%)
                </th>
                <th scope="col" className="px-3 py-2.5 text-right">
                  Sem Bio Até 17h
                </th>
                <th scope="col" className="px-3 py-2.5 text-right">
                  Sem Bio Pós-17h
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {municipalities.map((m) => (
                <tr key={m.municipio_cod} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-medium text-slate-900 flex items-center gap-1.5">
                    <Building className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
                    <span>{m.municipio_nome}</span>
                  </td>
                  <td className="px-3 py-2.5 text-center font-mono text-slate-500">
                    {m.municipio_cod}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {formatNumber(m.total_secoes_analisadas)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-medium">
                    {formatNumber(m.total_votos)}
                  </td>
                  <td className="px-3 py-2.5 text-right text-indigo-700 font-semibold">
                    {formatPercent(m.pct_votos_apos_17h)}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {formatPercent(m.pct_sem_bio_ate_17h)}
                  </td>
                  <td className="px-3 py-2.5 text-right text-emerald-700 font-semibold">
                    {formatPercent(m.pct_sem_bio_apos_17h)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
