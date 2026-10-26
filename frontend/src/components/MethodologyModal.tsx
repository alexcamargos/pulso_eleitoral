"use client";

import React, { useEffect, useRef } from "react";
import { X, CheckCircle2, AlertTriangle, ShieldCheck, Clock } from "lucide-react";
import { MetadataPayload } from "../types/audit";

interface MethodologyModalProps {
  isOpen: boolean;
  onClose: () => void;
  metadata: MetadataPayload | null;
}

export const MethodologyModal: React.FC<MethodologyModalProps> = ({
  isOpen,
  onClose,
  metadata,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
      modalRef.current?.focus();
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      ref={modalRef}
      tabIndex={-1}
    >
      <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col border border-slate-200 overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-blue-400" aria-hidden="true" />
            <h2 id="modal-title" className="text-lg font-bold">
              Transparência Metodológica & Notas de Integridade
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors focus:ring-2 focus:ring-blue-400"
            aria-label="Fechar janela de metodologia"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-sm text-slate-700 leading-relaxed">
          {/* Seção 1: Regra Legal das Filas */}
          <div className="border-l-4 border-blue-500 pl-4 py-1">
            <h3 className="font-semibold text-slate-900 text-base flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-600" aria-hidden="true" />
              1. Encerramento da Votação e Distribuição de Senhas pós-17h
            </h3>
            <p className="mt-1">
              Nos termos do Código Eleitoral (Lei nº 4.737/1965, art. 149) e da Resolução TSE nº 23.669/2021
              (art. 153), a votação encerra-se oficialmente às 17h00. Todos os eleitores presentes na fila até esse
              horário <strong>têm direito garantido ao voto</strong> mediante a entrega de senhas numeradas em ordem decrescente pelos mesários.
              Portanto, a ocorrência de votos após as 17h00 decorre regularmente do exercício da cidadania em seções de elevado fluxo.
            </p>
          </div>

          {/* Seção 2: Normalização de Fuso Horário */}
          <div className="border-l-4 border-indigo-500 pl-4 py-1">
            <h3 className="font-semibold text-slate-900 text-base">
              2. Normalização Aritmética de Fuso Horário (BRT / UTC-3)
            </h3>
            <p className="mt-1">
              A partir das Eleições Gerais de 2022 (Resolução TSE nº 23.669/2021, art. 144), o horário de início e
              encerramento da votação foi <strong>unificado em todo o território nacional</strong> no Horário de Brasília (BRT, UTC-3).
              O pipeline realiza a normalização aritmética exata do relógio interno de cada urna considerando o fuso de cada um dos
              5.570 municípios brasileiros (de Fernando de Noronha UTC-2 até o extremo oeste do Amazonas UTC-5).
            </p>
          </div>

          {/* Seção 3: Outlier Estatístico vs. Irregularidade Material */}
          <div className="border-l-4 border-amber-500 pl-4 py-1">
            <h3 className="font-semibold text-slate-900 text-base flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" aria-hidden="true" />
              3. Distinção Estatística: Outlier vs. Irregularidade Material
            </h3>
            <p className="mt-1">
              A classificação de seções em Tiers analíticos tem finalidade exclusivamente estatística e descritiva:
            </p>
            <ul className="list-disc list-inside mt-2 space-y-1 text-slate-600">
              <li>
                <strong>TIER 1 (Informativo):</strong> Seções com voto pós-17h em que houve eleitores habilitados sem biometria.
              </li>
              <li>
                <strong>TIER 2 (Outlier Estatístico):</strong> Desvio relevante da linha de base estadual (Z-Score &ge; 3.0 e &ge; 10 votos pós-17h). Representa cauda estatística da distribuição amostral, comum em seções com falhas pontuais de leitor biométrico.
              </li>
              <li>
                <strong>TIER 3 (Anomalia Operacional):</strong> Inconsistência física ou operacional detectável no log (ex.: discrepância entre log e BU, desvio severo do relógio RTC ou voto registrado após comando formal de encerramento).
              </li>
            </ul>
          </div>

          {/* Seção 4: Integridade Criptográfica e Auditabilidade */}
          <div className="border-l-4 border-emerald-500 pl-4 py-1">
            <h3 className="font-semibold text-slate-900 text-base flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" aria-hidden="true" />
              4. Rastreabilidade Criptográfica e Independência de Auditoria
            </h3>
            <p className="mt-1">
              Todos os artefatos são calculados a partir de dados abertos brutos assinados digitalmente pelo TSE.
              Cada seção sinalizada contém link direto para o portal oficial <code>resultados.tse.jus.br</code> para permitir
              conferência independente pelo cidadão.
            </p>
            {metadata && (
              <div className="mt-3 p-3 bg-slate-100 rounded border border-slate-200 text-xs font-mono space-y-1">
                <div>Versão do Pipeline: <strong>{metadata.pipeline_version}</strong></div>
                <div>Hash SHA-256 do Banco Analítico DuckDB:</div>
                <div className="break-all text-blue-700 font-semibold">{metadata.duckdb_sha256}</div>
                <div>Data/Hora de Geração: {metadata.generated_at}</div>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-medium transition-colors focus:ring-2 focus:ring-slate-400"
          >
            Entendido e Fechar
          </button>
        </div>
      </div>
    </div>
  );
};
