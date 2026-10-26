"use client";

import React, { useState, useMemo } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown, ChevronRight, Search } from "lucide-react";
import { StateSummaryItem } from "../types/audit";
import { formatNumber, formatPercent } from "../lib/api";

interface StatesTableProps {
  states: StateSummaryItem[];
  selectedUf: string | null;
  onSelectUf: (uf: string) => void;
  loading: boolean;
}

type SortField =
  | "uf"
  | "total_votos"
  | "votos_apos_17h"
  | "pct_votos_apos_17h"
  | "pct_sem_bio_ate_17h"
  | "pct_sem_bio_apos_17h"
  | "tier_2_outliers_count"
  | "tier_3_anomalies_count";

export const StatesTable: React.FC<StatesTableProps> = ({
  states,
  selectedUf,
  onSelectUf,
  loading,
}) => {
  const [sortField, setSortField] = useState<SortField>("total_votos");
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>("");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const filteredAndSortedStates = useMemo(() => {
    let result = states.filter((s) =>
      s.uf.toLowerCase().includes(searchTerm.toLowerCase())
    );

    result = [...result].sort((a, b) => {
      const valA = a[sortField];
      const valB = b[sortField];
      if (typeof valA === "string" && typeof valB === "string") {
        return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return sortAsc
        ? (valA as number) - (valB as number)
        : (valB as number) - (valA as number);
    });

    return result;
  }, [states, sortField, sortAsc, searchTerm]);

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 text-slate-400 ml-1 inline" />;
    }
    return sortAsc ? (
      <ArrowUp className="w-3.5 h-3.5 text-blue-600 ml-1 inline" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-blue-600 ml-1 inline" />
    );
  };

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-xl border border-slate-200 animate-pulse h-64"></div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Table Header / Search */}
      <div className="p-4 bg-slate-50 border-b border-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-900">
            Comparativo Regional por Unidade Federativa (27 UFs)
          </h2>
          <p className="text-xs text-slate-500">
            Clique em uma linha para detalhar municípios e seções sinalizadas
          </p>
        </div>
        <div className="relative w-full sm:w-48">
          <label htmlFor="uf-search" className="sr-only">
            Buscar UF
          </label>
          <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" aria-hidden="true" />
          <input
            id="uf-search"
            type="text"
            placeholder="Filtrar UF..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          />
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left text-slate-700">
          <thead className="bg-slate-100 text-slate-700 uppercase font-semibold border-b border-slate-200">
            <tr>
              <th
                scope="col"
                className="px-4 py-3 cursor-pointer hover:bg-slate-200 transition-colors"
                onClick={() => handleSort("uf")}
                aria-sort={sortField === "uf" ? (sortAsc ? "ascending" : "descending") : "none"}
              >
                UF {renderSortIcon("uf")}
              </th>
              <th
                scope="col"
                className="px-3 py-3 text-right cursor-pointer hover:bg-slate-200 transition-colors"
                onClick={() => handleSort("total_votos")}
                aria-sort={sortField === "total_votos" ? (sortAsc ? "ascending" : "descending") : "none"}
              >
                Total Votos {renderSortIcon("total_votos")}
              </th>
              <th
                scope="col"
                className="px-3 py-3 text-right cursor-pointer hover:bg-slate-200 transition-colors"
                onClick={() => handleSort("pct_votos_apos_17h")}
                aria-sort={sortField === "pct_votos_apos_17h" ? (sortAsc ? "ascending" : "descending") : "none"}
              >
                Pós-17h (%) {renderSortIcon("pct_votos_apos_17h")}
              </th>
              <th
                scope="col"
                className="px-3 py-3 text-right cursor-pointer hover:bg-slate-200 transition-colors"
                onClick={() => handleSort("pct_sem_bio_ate_17h")}
                aria-sort={sortField === "pct_sem_bio_ate_17h" ? (sortAsc ? "ascending" : "descending") : "none"}
              >
                Sem Bio Até 17h {renderSortIcon("pct_sem_bio_ate_17h")}
              </th>
              <th
                scope="col"
                className="px-3 py-3 text-right cursor-pointer hover:bg-slate-200 transition-colors"
                onClick={() => handleSort("pct_sem_bio_apos_17h")}
                aria-sort={sortField === "pct_sem_bio_apos_17h" ? (sortAsc ? "ascending" : "descending") : "none"}
              >
                Sem Bio Pós-17h {renderSortIcon("pct_sem_bio_apos_17h")}
              </th>
              <th
                scope="col"
                className="px-3 py-3 text-center cursor-pointer hover:bg-slate-200 transition-colors"
                onClick={() => handleSort("tier_2_outliers_count")}
                aria-sort={sortField === "tier_2_outliers_count" ? (sortAsc ? "ascending" : "descending") : "none"}
              >
                Tier 2 (Outliers) {renderSortIcon("tier_2_outliers_count")}
              </th>
              <th
                scope="col"
                className="px-3 py-3 text-center cursor-pointer hover:bg-slate-200 transition-colors"
                onClick={() => handleSort("tier_3_anomalies_count")}
                aria-sort={sortField === "tier_3_anomalies_count" ? (sortAsc ? "ascending" : "descending") : "none"}
              >
                Tier 3 (Anomalias) {renderSortIcon("tier_3_anomalies_count")}
              </th>
              <th scope="col" className="px-3 py-3 text-center">
                Ação
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredAndSortedStates.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-6 text-slate-500">
                  Nenhuma UF encontrada com o filtro aplicado.
                </td>
              </tr>
            ) : (
              filteredAndSortedStates.map((st) => {
                const isSelected = selectedUf === st.uf;
                return (
                  <tr
                    key={st.uf}
                    onClick={() => onSelectUf(st.uf)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelectUf(st.uf);
                      }
                    }}
                    tabIndex={0}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-blue-50 font-semibold text-blue-900 border-l-4 border-blue-600"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <td className="px-4 py-3 font-bold text-slate-900 flex items-center gap-1.5">
                      <span>{st.uf}</span>
                      {isSelected && (
                        <span className="text-[10px] bg-blue-600 text-white px-1.5 py-0.2 rounded">
                          Ativo
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-right">
                      {formatNumber(st.total_votos)}
                    </td>
                    <td className="px-3 py-3 text-right font-medium text-indigo-700">
                      {formatPercent(st.pct_votos_apos_17h)}
                    </td>
                    <td className="px-3 py-3 text-right">
                      {formatPercent(st.pct_sem_bio_ate_17h)}
                    </td>
                    <td className="px-3 py-3 text-right font-medium text-emerald-700">
                      {formatPercent(st.pct_sem_bio_apos_17h)}
                    </td>
                    <td className="px-3 py-3 text-center">
                      {st.tier_2_outliers_count > 0 ? (
                        <span className="bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full text-[11px]">
                          {st.tier_2_outliers_count}
                        </span>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-center">
                      {st.tier_3_anomalies_count > 0 ? (
                        <span className="bg-rose-100 text-rose-800 font-bold px-2 py-0.5 rounded-full text-[11px]">
                          {st.tier_3_anomalies_count}
                        </span>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectUf(st.uf);
                        }}
                        className="text-blue-600 hover:text-blue-800 p-1 rounded hover:bg-blue-100"
                        aria-label={`Detalhar municípios da UF ${st.uf}`}
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
