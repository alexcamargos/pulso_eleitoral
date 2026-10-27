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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#0E1117]/85 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      ref={modalRef}
      tabIndex={-1}
    >
      <div className="bg-[#181B20] rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col border border-[#282D37] overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-[#121417] text-[#F8FAFC] flex items-center justify-between border-b border-[#282D37]">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-[#38BDF8]" aria-hidden="true" />
            <h2 id="modal-title" className="text-base sm:text-lg font-bold">
              Transparência Metodológica & Notas de Integridade
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-[#94A3B8] hover:text-[#F8FAFC] p-1.5 rounded-lg hover:bg-[#242933] transition-colors"
            aria-label="Fechar janela de metodologia"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs sm:text-sm text-[#CBD5E1] leading-relaxed">
          {/* Seção 1: Regra Legal das Filas */}
          <div className="border-l-4 border-l-[#38BDF8] pl-4 py-1">
            <h3 className="font-bold text-[#F8FAFC] text-sm flex items-center gap-2">
              <Clock className="w-4 h-4 text-[#38BDF8]" aria-hidden="true" />
              1. Encerramento da Votação e Distribuição de Senhas pós-17h
            </h3>
            <p className="mt-1 text-[#94A3B8]">
              Nos termos do Código Eleitoral (Lei nº 4.737/1965, art. 149) e das resoluções oficiais do TSE,
              a votação encerra-se oficialmente às 17h00. Todos os eleitores presentes na fila até esse
              horário <strong className="text-[#CBD5E1]">têm direito garantido ao voto</strong> mediante a entrega de senhas numeradas
              pelos mesários. Portanto, a ocorrência de votos após as 17h00 decorre regularmente do exercício do sufrágio em seções com fluxo concentrado.
            </p>
          </div>

          {/* Seção 2: Normalização de Fuso Horário */}
          <div className="border-l-4 border-l-[#818CF8] pl-4 py-1">
            <h3 className="font-bold text-[#F8FAFC] text-sm">
              2. Normalização Aritmética de Fuso Horário (BRT / UTC-3)
            </h3>
            <p className="mt-1 text-[#94A3B8]">
              A partir das Eleições Gerais de 2022, o horário de início e encerramento da votação foi{" "}
              <strong className="text-[#CBD5E1]">unificado em todo o território nacional</strong> no Horário de Brasília (BRT, UTC-3).
              O pipeline realiza a normalização aritmética exata do relógio interno de cada urna considerando o fuso de cada um dos
              5.570 municípios brasileiros (de Fernando de Noronha UTC-2 até o extremo oeste do Amazonas UTC-5).
            </p>
          </div>

          {/* Seção 3: Outlier Estatístico vs. Irregularidade Material */}
          <div className="border-l-4 border-l-[#F59E0B] pl-4 py-1">
            <h3 className="font-bold text-[#F8FAFC] text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-[#F59E0B]" aria-hidden="true" />
              3. Distinção Estatística: Outlier vs. Irregularidade Material
            </h3>
            <p className="mt-1 text-[#94A3B8]">
              A classificação de seções em Tiers analíticos tem finalidade exclusivamente estatística e descritiva:
            </p>
            <ul className="list-disc list-inside mt-2 space-y-1 text-[#94A3B8]">
              <li>
                <strong className="text-[#CBD5E1]">TIER 1 (Informativo):</strong> Seções com voto pós-17h em que houve eleitores habilitados sem biometria.
              </li>
              <li>
                <strong className="text-[#CBD5E1]">TIER 2 (Outlier Estatístico):</strong> Desvio relevante da linha de base estadual (Z-Score &ge; 3.0 e &ge; 10 votos pós-17h). Representa cauda estatística da distribuição amostral.
              </li>
              <li>
                <strong className="text-[#CBD5E1]">TIER 3 (Anomalia Operacional):</strong> Inconsistência física no log (discrepância entre log e BU, desvio severo do relógio RTC ou voto registrado após comando formal de encerramento).
              </li>
            </ul>
          </div>

          {/* Seção 4: Integridade Criptográfica e Auditabilidade */}
          <div className="border-l-4 border-l-[#10B981] pl-4 py-1">
            <h3 className="font-bold text-[#F8FAFC] text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#10B981]" aria-hidden="true" />
              4. Rastreabilidade Criptográfica e Independência de Auditoria
            </h3>
            <p className="mt-1 text-[#94A3B8]">
              Todos os artefatos são calculados a partir de dados abertos brutos assinados digitalmente pelo TSE.
              Cada seção contém link de checagem direta para o portal oficial <code className="text-[#38BDF8]">resultados.tse.jus.br</code>.
            </p>
            {metadata && (
              <div className="mt-3 p-3 bg-[#121417] rounded-lg border border-[#282D37] text-xs font-mono space-y-1.5">
                <div>Versão do Pipeline: <strong className="text-[#F8FAFC]">v{metadata.pipeline_version}</strong></div>
                <div>Hash SHA-256 do Banco Analítico DuckDB:</div>
                <div className="break-all text-[#38BDF8] font-bold">{metadata.duckdb_sha256}</div>
                <div className="text-[#64748B]">Data/Hora de Geração UTC: {metadata.generated_at}</div>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 bg-[#121417] border-t border-[#282D37] flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#242933] hover:bg-[#2d3442] text-[#F8FAFC] border border-[#282D37] rounded-lg text-xs font-semibold transition-colors"
          >
            Entendido e Fechar
          </button>
        </div>
      </div>
    </div>
  );
};
