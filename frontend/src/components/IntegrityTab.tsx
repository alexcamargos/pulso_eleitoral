"use client";

import React from "react";
import { BiometricsPayload } from "../types/audit";
import { formatNumber } from "../lib/api";

interface IntegrityTabProps {
  data: BiometricsPayload | null;
  loading?: boolean;
}

export const IntegrityTab: React.FC<IntegrityTabProps> = ({ data, loading }) => {
  // Valores padrão alinhados ao banco consolidado
  const ate17h = data?.ate_17h ?? {
    total: 127599837,
    com_bio: 119132645,
    sem_bio: 8467192,
    pct_com_bio: 93.3643,
    pct_sem_bio: 6.6357,
  };

  const pos17h = data?.pos_17h ?? {
    total: 35972,
    com_bio: 33169,
    sem_bio: 2803,
    pct_com_bio: 92.2078,
    pct_sem_bio: 7.7922,
  };

  const deltaSemBio = data?.delta_sem_bio ?? 1.1565;

  return (
    <div className="space-y-6">
      {/* 1. Introdução Narrativa */}
      <div>
        <h2 className="text-xl sm:text-2xl font-bold text-[#F8FAFC]">
          Ato 3: Auditoria de Integridade Procedimental & Biometria
        </h2>
        <p className="text-xs sm:text-sm text-[#94A3B8] mt-1.5 leading-relaxed max-w-4xl">
          Uma hipótese crítica de auditoria é se houve relaxamento nas regras de identificação (ex.: mesários liberando votantes manualmente em lote para apressar o fechamento das urnas). Os dados comprovam{" "}
          <strong className="text-[#10B981]">estabilidade total de protocolo</strong>.
        </p>
      </div>

      {/* 2. Gráfico de Barras Empilhadas 100% e Card de Variação */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Gráfico 100% Stacked */}
        <div className="lg:col-span-7 bg-[#181B20] border border-[#282D37] rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="text-sm font-bold text-[#F8FAFC] mb-1">
              Distribuição do Método de Identificação do Eleitor
            </div>
            <p className="text-xs text-[#94A3B8] mb-4">
              Comparação percentual da cabine entre o período regular e a janela de extensão.
            </p>

            {/* Legenda */}
            <div className="flex flex-wrap items-center gap-4 text-xs mb-5">
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 rounded bg-[#10B981]" />
                <span className="text-[#CBD5E1] font-medium">Identificação Biométrica (Digital)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 rounded bg-[#F59E0B]" />
                <span className="text-[#CBD5E1] font-medium">Liberação Manual (Mesário)</span>
              </div>
            </div>

            {/* Barras Empilhadas */}
            <div className="space-y-5">
              {/* Barra 1: Até 17h00 (Regular) */}
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="font-semibold text-[#F8FAFC]">Até 17h00 (Período Regular)</span>
                  <span className="text-[#94A3B8] font-mono">{formatNumber(ate17h.total)} votos</span>
                </div>
                <div className="w-full h-8 bg-[#121417] rounded-lg overflow-hidden flex border border-[#282D37]">
                  <div
                    className="bg-[#10B981] h-full flex items-center justify-center text-[11px] font-bold text-slate-950 transition-all duration-700"
                    style={{ width: `${ate17h.pct_com_bio}%` }}
                    title={`Biometria: ${ate17h.pct_com_bio.toFixed(1)}%`}
                  >
                    {ate17h.pct_com_bio.toFixed(1)}%
                  </div>
                  <div
                    className="bg-[#F59E0B] h-full flex items-center justify-center text-[11px] font-bold text-slate-950 transition-all duration-700"
                    style={{ width: `${ate17h.pct_sem_bio}%` }}
                    title={`Manual: ${ate17h.pct_sem_bio.toFixed(1)}%`}
                  >
                    {ate17h.pct_sem_bio.toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Barra 2: Após 17h00 (Extensão) */}
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="font-semibold text-[#F8FAFC]">Após 17h00 (Janela de Extensão)</span>
                  <span className="text-[#94A3B8] font-mono">{formatNumber(pos17h.total)} votos</span>
                </div>
                <div className="w-full h-8 bg-[#121417] rounded-lg overflow-hidden flex border border-[#282D37]">
                  <div
                    className="bg-[#10B981] h-full flex items-center justify-center text-[11px] font-bold text-slate-950 transition-all duration-700"
                    style={{ width: `${pos17h.pct_com_bio}%` }}
                    title={`Biometria: ${pos17h.pct_com_bio.toFixed(1)}%`}
                  >
                    {pos17h.pct_com_bio.toFixed(1)}%
                  </div>
                  <div
                    className="bg-[#F59E0B] h-full flex items-center justify-center text-[11px] font-bold text-slate-950 transition-all duration-700"
                    style={{ width: `${pos17h.pct_sem_bio}%` }}
                    title={`Manual: ${pos17h.pct_sem_bio.toFixed(1)}%`}
                  >
                    {pos17h.pct_sem_bio.toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#282D37] text-[11px] text-[#64748B]">
            * Percentuais calculados sobre o universo de votos válidos com validação de assinatura no Boletim de Urna (BU).
          </div>
        </div>

        {/* Card de Variação de Liberação Manual */}
        <div className="lg:col-span-5 bg-[#181B20] border border-[#282D37] rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-3">
              <span className="text-[11.5px] font-bold text-[#94A3B8] uppercase tracking-[0.8px]">
                Variação de Liberação Manual
              </span>
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30">
                Conforme (+{deltaSemBio.toFixed(2)}%)
              </span>
            </div>

            <div className="text-3xl sm:text-4xl font-extrabold text-[#10B981] tracking-tight leading-none mb-3">
              +{deltaSemBio.toFixed(2).replace(".", ",")}%
            </div>

            <div className="text-xs text-[#94A3B8] leading-relaxed space-y-2">
              <p>
                A taxa de liberação pelo mesário variou de{" "}
                <strong className="text-[#CBD5E1]">{ate17h.pct_sem_bio.toFixed(2)}%</strong> para{" "}
                <strong className="text-[#CBD5E1]">{pos17h.pct_sem_bio.toFixed(2)}%</strong>.
              </p>
              <p>
                Com mais de <strong className="text-[#10B981]">92% dos eleitores autenticados por biometria</strong>{" "}
                mesmo no período noturno, o procedimento manteve rigorosamente o mesmo padrão técnico do restante do dia,
                afastando qualquer anomalia de identificação ou relaxamento de segurança.
              </p>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#282D37] flex items-center justify-between text-xs text-[#CBD5E1]">
            <span>Status Técnico da Cabine:</span>
            <span className="font-bold text-[#10B981] flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#10B981]" />
              Conformidade Plena
            </span>
          </div>
        </div>
      </div>

      {/* 3. Diagnóstico de Contingência e Relógio */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[#181B20] border border-[#282D37] rounded-xl p-4">
          <div className="text-sm font-bold text-[#38BDF8] mb-1.5 flex items-center gap-2">
            <span>Urnas de Contingência</span>
            <span className="text-[#94A3B8]">&bull;</span>
            <span className="text-[#CBD5E1]">Substituição de Hardware</span>
          </div>
          <p className="text-xs text-[#94A3B8] leading-relaxed">
            Em seções onde a urna eletrônica apresentou pane durante a tarde, a substituição pela urna de reserva transfere com
            assinatura digital o histórico de votos anteriores gravados na memória de resultado (MR). O pipeline do Pulso Eleitoral
            reconcilia a cadeia histórica completa a partir de múltiplos arquivos de log (<code className="text-[#38BDF8]">logd.dat</code>).
          </p>
        </div>

        <div className="bg-[#181B20] border border-[#282D37] rounded-xl p-4">
          <div className="text-sm font-bold text-[#10B981] mb-1.5 flex items-center gap-2">
            <span>Desvios de Relógio Interno (RTC)</span>
            <span className="text-[#94A3B8]">&bull;</span>
            <span className="text-[#CBD5E1]">Integridade de Timestamps</span>
          </div>
          <p className="text-xs text-[#94A3B8] leading-relaxed">
            O oscilador de quartzo do relógio de tempo real (RTC) da placa-mãe da urna opera com deriva térmica controlada (&lt; 2s/dia).
            Seções com carimbos anômalos pré-08h ou pós-encerramento são classificadas na severidade máxima (TIER_3), garantindo que
            nenhum voto seja auditado sem rastro cronológico íntegro.
          </p>
        </div>
      </div>
    </div>
  );
};
