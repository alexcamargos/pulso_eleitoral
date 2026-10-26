"use client";

import React, { useState, useMemo } from "react";
import { ExternalLink, Filter, AlertTriangle, AlertCircle, Info, Search } from "lucide-react";
import { FlaggedSectionItem } from "../types/audit";
import { formatNumber, formatPercent, getTseResultUrl } from "../lib/api";

interface FlaggedSectionsTableProps {
  sections: FlaggedSectionItem[];
  ano: number;
  loading: boolean;
  activeUf: string | null;
}

export const FlaggedSectionsTable: React.FC<FlaggedSectionsTableProps> = ({
  sections,
  ano,
  loading,
  activeUf,
}) => {
  const [selectedTier, setSelectedTier] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const filteredSections = useMemo(() => {
    return sections.filter((sec) => {
      // Filtro de Tier
      if (selectedTier !== "ALL" && sec.severidade_sinalizacao !== selectedTier) {
        return false;
      }
      // Filtro de Busca (Município, Zona, Seção)
      if (searchQuery.trim() !== "") {
        const q = searchQuery.toLowerCase().trim();
        const matchesMun = sec.municipio_nome.toLowerCase().includes(q);
        const matchesZonaSec =
          `zona ${sec.zona} secao ${sec.secao}`.includes(q) ||
          `${sec.zona}/${sec.secao}`.includes(q) ||
          String(sec.secao) === q ||
          String(sec.zona) === q;
        if (!matchesMun && !matchesZonaSec) return false;
      }
      return true;
    });
  }, [sections, selectedTier, searchQuery]);

  const renderTierBadge = (tier: string) => {
    switch (tier) {
      case "TIER_3_CRITICAL_ANOMALY":
        return (
          <span className="inline-flex items-center gap-1 bg-rose-100 text-rose-800 border border-rose-200 px-2 py-0.5 rounded text-[11px] font-bold">
            <AlertCircle className="w-3 h-3 text-rose-600" aria-hidden="true" />
            Tier 3 (Anomalia)
          </span>
        );
      case "TIER_2_STATISTICAL_OUTLIER":
        return (
          <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 border border-amber-200 px-2 py-0.5 rounded text-[11px] font-bold">
            <AlertTriangle className="w-3 h-3 text-amber-600" aria-hidden="true" />
            Tier 2 (Outlier)
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 border border-blue-200 px-2 py-0.5 rounded text-[11px] font-medium">
            <Info className="w-3 h-3 text-blue-600" aria-hidden="true" />
            Tier 1 (Fila)
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-xl border border-slate-200 animate-pulse h-64 mt-6"></div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mt-6">
      {/* Header and Controls */}
      <div className="p-4 bg-slate-50 border-b border-slate-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <span>Explorador Auditável de Seções Sinalizadas</span>
            {activeUf ? (
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded font-semibold">
                Filtro UF: {activeUf}
              </span>
            ) : (
              <span className="text-xs bg-slate-200 text-slate-700 px-2 py-0.5 rounded font-normal">
                Top 1.000 Nacional
              </span>
            )}
          </h2>
          <p className="text-xs text-slate-500">
            Exibindo {filteredSections.length} de {sections.length} seções carregadas. Clique no link para verificar no TSE.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          {/* Seletor de Severidade */}
          <div className="flex items-center gap-1.5 bg-white border border-slate-300 rounded-lg px-2 py-1">
            <Filter className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
            <label htmlFor="tier-filter" className="text-xs text-slate-600 font-medium">
              Severidade:
            </label>
            <select
              id="tier-filter"
              value={selectedTier}
              onChange={(e) => setSelectedTier(e.target.value)}
              className="text-xs text-slate-800 bg-transparent outline-none cursor-pointer"
            >
              <option value="ALL">Todas as Severidades</option>
              <option value="TIER_3_CRITICAL_ANOMALY">Tier 3 — Anomalia Crítica</option>
              <option value="TIER_2_STATISTICAL_OUTLIER">Tier 2 — Outlier Estatístico</option>
              <option value="TIER_1_POST_17H_NO_BIO">Tier 1 — Fila pós-17h</option>
            </select>
          </div>

          {/* Busca por Município/Zona/Seção */}
          <div className="relative flex-1 md:w-48">
            <label htmlFor="section-search" className="sr-only">
              Buscar seção eleitoral
            </label>
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" aria-hidden="true" />
            <input
              id="section-search"
              type="text"
              placeholder="Município, Zona ou Seção..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1 text-xs bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto max-h-[600px]">
        <table className="w-full text-xs text-left text-slate-700">
          <thead className="bg-slate-100 text-slate-700 uppercase font-semibold sticky top-0 border-b border-slate-200">
            <tr>
              <th scope="col" className="px-3 py-2.5">
                Localização (UF / Mun / Zona / Seção)
              </th>
              <th scope="col" className="px-3 py-2.5 text-center">
                Severidade
              </th>
              <th scope="col" className="px-3 py-2.5 text-right">
                Total Votos
              </th>
              <th scope="col" className="px-3 py-2.5 text-right">
                Pós-17h (%)
              </th>
              <th scope="col" className="px-3 py-2.5 text-right">
                Sem Bio Até 17h
              </th>
              <th scope="col" className="px-3 py-2.5 text-right">
                Sem Bio Pós-17h
              </th>
              <th scope="col" className="px-3 py-2.5 text-right">
                Delta / Z-Score
              </th>
              <th scope="col" className="px-3 py-2.5 text-center">
                Último Voto (BRT)
              </th>
              <th scope="col" className="px-3 py-2.5 text-center">
                Auditoria TSE
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredSections.length === 0 ? (
              <tr>
                <td colSpan={9} className="text-center py-8 text-slate-500">
                  Nenhuma seção eleitoral encontrada para os filtros selecionados.
                </td>
              </tr>
            ) : (
              filteredSections.map((sec, idx) => {
                const tseUrl = getTseResultUrl(
                  ano,
                  sec.uf,
                  sec.municipio_cod,
                  sec.zona,
                  sec.secao
                );
                return (
                  <tr key={`${sec.uf}-${sec.zona}-${sec.secao}-${idx}`} className="hover:bg-slate-50">
                    <td className="px-3 py-2.5 font-medium text-slate-900">
                      <div>
                        <span className="font-bold text-blue-700 mr-1.5">{sec.uf}</span>
                        <span>{sec.municipio_nome}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        Zona: {sec.zona} | Seção: {sec.secao}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-center whitespace-nowrap">
                      {renderTierBadge(sec.severidade_sinalizacao)}
                    </td>
                    <td className="px-3 py-2.5 text-right font-medium">
                      {formatNumber(sec.total_votos)}
                    </td>
                    <td className="px-3 py-2.5 text-right text-indigo-700 font-semibold">
                      {formatPercent(sec.pct_votos_apos_17h)}
                      <div className="text-[10px] text-slate-400 font-normal">
                        ({sec.votos_apos_17h} votos)
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {formatPercent(sec.pct_sem_bio_ate_17h)}
                    </td>
                    <td className="px-3 py-2.5 text-right text-emerald-700 font-semibold">
                      {formatPercent(sec.pct_sem_bio_apos_17h)}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <span className="font-semibold text-slate-800">
                        {sec.delta_sem_bio_pp > 0 ? `+${sec.delta_sem_bio_pp.toFixed(1)}` : sec.delta_sem_bio_pp.toFixed(1)} p.p.
                      </span>
                      {sec.z_score_uf_pos_17h > 0 && (
                        <div className="text-[10px] text-amber-700 font-mono">
                          Z: {sec.z_score_uf_pos_17h.toFixed(2)}σ
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-center text-slate-600 font-mono text-[11px] whitespace-nowrap">
                      {sec.horario_ultimo_voto_brt
                        ? sec.horario_ultimo_voto_brt.split("T")[1]?.slice(0, 8) || sec.horario_ultimo_voto_brt
                        : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <a
                        href={tseUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 hover:underline font-medium text-[11px] p-1 rounded hover:bg-blue-50 focus:ring-2 focus:ring-blue-400"
                        title={`Auditar Seção ${sec.secao} no Portal Oficial de Resultados do TSE`}
                        aria-label={`Auditar Seção ${sec.secao} da Zona ${sec.zona} no portal do TSE`}
                      >
                        <span>Ver TSE</span>
                        <ExternalLink className="w-3 h-3" aria-hidden="true" />
                      </a>
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
