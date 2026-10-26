"use client";

import React from "react";
import { Vote, Clock, Fingerprint, AlertCircle } from "lucide-react";
import { NationalSummaryPayload } from "../types/audit";
import { formatNumber, formatPercent } from "../lib/api";

interface KpiCardsProps {
  summary: NationalSummaryPayload | null;
  loading: boolean;
}

export const KpiCards: React.FC<KpiCardsProps> = ({ summary, loading }) => {
  if (loading || !summary) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-32 bg-slate-200 rounded-xl"></div>
        ))}
      </div>
    );
  }

  const {
    total_votos_brasil,
    total_secoes_analisadas,
    total_secoes_manifesto,
    cobertura_secoes_pct,
    total_secoes_nao_processadas,
    votos_apos_17h_brasil,
    pct_apos_17h,
    pct_sem_bio_ate_17h,
    pct_sem_bio_apos_17h,
    flagged_counts_by_tier,
  } = summary;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Card 1: Votos Auditados & Cobertura */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Votos Auditados
          </span>
          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg" aria-hidden="true">
            <Vote className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-2">
          <div className="text-2xl font-bold text-slate-900">
            {formatNumber(total_votos_brasil)}
          </div>
          <div className="text-xs text-slate-500 mt-1 flex items-center justify-between">
            <span>Cobertura: {formatPercent(cobertura_secoes_pct)}</span>
            <span title={`${total_secoes_analisadas} analisadas de ${total_secoes_manifesto} manifestadas`}>
              {formatNumber(total_secoes_analisadas)} seções
            </span>
          </div>
          {total_secoes_nao_processadas > 0 && (
            <div className="text-[11px] text-amber-600 mt-1 font-medium">
              {formatNumber(total_secoes_nao_processadas)} não processadas
            </div>
          )}
        </div>
      </div>

      {/* Card 2: Votos Pós-17h */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Votos Pós-17h (BRT)
          </span>
          <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg" aria-hidden="true">
            <Clock className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-2">
          <div className="text-2xl font-bold text-indigo-700">
            {formatNumber(votos_apos_17h_brasil)}
          </div>
          <div className="text-xs text-slate-500 mt-1 flex items-center justify-between">
            <span>Fatia do Total:</span>
            <strong className="text-slate-800">{formatPercent(pct_apos_17h)}</strong>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            Filas com senha na regra legal
          </div>
        </div>
      </div>

      {/* Card 3: Sem Biometria (Pré vs Pós 17h) */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Habilitação Sem Biometria
          </span>
          <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg" aria-hidden="true">
            <Fingerprint className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-2">
          <div className="flex items-baseline justify-between">
            <div>
              <span className="text-[10px] text-slate-500 block uppercase">Até 17h</span>
              <span className="text-lg font-bold text-slate-700">
                {formatPercent(pct_sem_bio_ate_17h)}
              </span>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-slate-500 block uppercase">Pós-17h</span>
              <span className="text-lg font-bold text-emerald-700">
                {formatPercent(pct_sem_bio_apos_17h)}
              </span>
            </div>
          </div>
          <div className="text-[11px] text-slate-500 mt-2 border-t pt-1 flex justify-between">
            <span>Delta Nacional:</span>
            <span className="font-semibold text-slate-700">
              {(pct_sem_bio_apos_17h - pct_sem_bio_ate_17h).toFixed(2)} p.p.
            </span>
          </div>
        </div>
      </div>

      {/* Card 4: Seções Sinalizadas por Tier */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Seções Sinalizadas
          </span>
          <div className="p-2 bg-rose-50 text-rose-600 rounded-lg" aria-hidden="true">
            <AlertCircle className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-2 space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-rose-700 font-medium">Tier 3 (Anomalia):</span>
            <span className="font-bold bg-rose-100 text-rose-800 px-1.5 py-0.5 rounded">
              {formatNumber(flagged_counts_by_tier.TIER_3_CRITICAL_ANOMALY)}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-amber-700 font-medium">Tier 2 (Outlier):</span>
            <span className="font-bold bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">
              {formatNumber(flagged_counts_by_tier.TIER_2_STATISTICAL_OUTLIER)}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-blue-700 font-medium">Tier 1 (Fila pós-17h):</span>
            <span className="font-bold bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded">
              {formatNumber(flagged_counts_by_tier.TIER_1_POST_17H_NO_BIO)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
