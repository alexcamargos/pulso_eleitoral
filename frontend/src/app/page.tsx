"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Header } from "../components/Header";
import { KpiCards } from "../components/KpiCards";
import { StatesTable } from "../components/StatesTable";
import { MunicipalDrilldown } from "../components/MunicipalDrilldown";
import { FlaggedSectionsTable } from "../components/FlaggedSectionsTable";
import { MethodologyModal } from "../components/MethodologyModal";
import {
  MetadataPayload,
  NationalSummaryPayload,
  StatesSummaryPayload,
  MunicipalitiesPayload,
  FlaggedSectionsPayload,
} from "../types/audit";
import {
  fetchMetadata,
  fetchNationalSummary,
  fetchStatesSummary,
  fetchMunicipalities,
  fetchFlaggedSections,
} from "../lib/api";

export default function HomePage() {
  const [ano, setAno] = useState<number>(2022);
  const [turno, setTurno] = useState<number>(1);
  const [selectedUf, setSelectedUf] = useState<string | null>(null);

  const [metadata, setMetadata] = useState<MetadataPayload | null>(null);
  const [nationalSummary, setNationalSummary] = useState<NationalSummaryPayload | null>(null);
  const [statesSummary, setStatesSummary] = useState<StatesSummaryPayload | null>(null);
  const [municipalitiesData, setMunicipalitiesData] = useState<MunicipalitiesPayload | null>(null);
  const [flaggedSectionsData, setFlaggedSectionsData] = useState<FlaggedSectionsPayload | null>(null);

  const [loadingGeneral, setLoadingGeneral] = useState<boolean>(true);
  const [loadingMunicipalities, setLoadingMunicipalities] = useState<boolean>(false);
  const [isMethodologyOpen, setIsMethodologyOpen] = useState<boolean>(false);

  // Carrega dados nacionais e estaduais ao trocar ano/turno
  const loadGeneralData = useCallback(async (year: number, round: number) => {
    setLoadingGeneral(true);
    try {
      const [meta, nat, states, flagged] = await Promise.all([
        fetchMetadata(year, round),
        fetchNationalSummary(year, round),
        fetchStatesSummary(year, round),
        fetchFlaggedSections(undefined, year, round),
      ]);
      setMetadata(meta);
      setNationalSummary(nat);
      setStatesSummary(states);
      setFlaggedSectionsData(flagged);
    } catch (err) {
      console.error("Erro ao carregar dados do dashboard:", err);
    } finally {
      setLoadingGeneral(false);
    }
  }, []);

  useEffect(() => {
    loadGeneralData(ano, turno);
  }, [ano, turno, loadGeneralData]);

  // Carrega municípios e seções da UF quando uma UF é selecionada
  const handleSelectUf = async (uf: string) => {
    if (selectedUf === uf) {
      // Toggle off
      setSelectedUf(null);
      setMunicipalitiesData(null);
      // Recarrega flagged sections nacional
      const flagged = await fetchFlaggedSections(undefined, ano, turno);
      setFlaggedSectionsData(flagged);
      return;
    }

    setSelectedUf(uf);
    setLoadingMunicipalities(true);
    try {
      const [mun, flagged] = await Promise.all([
        fetchMunicipalities(uf, ano, turno),
        fetchFlaggedSections(uf, ano, turno),
      ]);
      setMunicipalitiesData(mun);
      if (flagged && flagged.items.length > 0) {
        setFlaggedSectionsData(flagged);
      }
    } catch (err) {
      console.error(`Erro ao carregar dados da UF ${uf}:`, err);
    } finally {
      setLoadingMunicipalities(false);
    }
  };

  const handleClearUf = async () => {
    setSelectedUf(null);
    setMunicipalitiesData(null);
    const flagged = await fetchFlaggedSections(undefined, ano, turno);
    setFlaggedSectionsData(flagged);
  };

  const handleSelectElection = (newAno: number, newTurno: number) => {
    setAno(newAno);
    setTurno(newTurno);
    setSelectedUf(null);
    setMunicipalitiesData(null);
  };

  return (
    <>
      <Header
        metadata={metadata}
        ano={ano}
        turno={turno}
        onSelectElection={handleSelectElection}
        onOpenMethodology={() => setIsMethodologyOpen(true)}
      />

      <main id="main-content" className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full">
        {/* Banner Informativo Rápido */}
        <section
          aria-label="Aviso Legal e Metodológico"
          className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-xl text-xs text-blue-900 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm"
        >
          <div>
            <strong>Auditoria Cidadã Independente:</strong> Dados abertos oficiais do Tribunal Superior Eleitoral (TSE).
            Horários normalizados para o Horário de Brasília (BRT / UTC-3). Eleitores na fila às 17h00 têm direito ao voto por senha legal.
          </div>
          <button
            onClick={() => setIsMethodologyOpen(true)}
            className="text-blue-700 underline font-semibold whitespace-nowrap hover:text-blue-900"
          >
            Ler notas metodológicas completas &rarr;
          </button>
        </section>

        {/* KPIs Nacionais */}
        <section aria-label="Indicadores Nacionais" className="mb-6">
          <KpiCards summary={nationalSummary} loading={loadingGeneral} />
        </section>

        {/* Comparativo Regional (27 UFs) */}
        <section aria-label="Comparativo por Unidade Federativa" className="mb-6">
          <StatesTable
            states={statesSummary?.states || []}
            selectedUf={selectedUf}
            onSelectUf={handleSelectUf}
            loading={loadingGeneral}
          />
        </section>

        {/* Drill-down Municipal (quando UF selecionada) */}
        {selectedUf && (
          <section aria-label="Detalhamento Municipal">
            <MunicipalDrilldown
              data={municipalitiesData}
              uf={selectedUf}
              loading={loadingMunicipalities}
              onClearUf={handleClearUf}
            />
          </section>
        )}

        {/* Explorador de Seções Sinalizadas */}
        <section aria-label="Explorador de Seções Sinalizadas" className="mb-8">
          <FlaggedSectionsTable
            sections={flaggedSectionsData?.items || []}
            ano={ano}
            loading={loadingGeneral}
            activeUf={selectedUf}
          />
        </section>
      </main>

      {/* Rodapé de Governança e Transparência */}
      <footer className="bg-slate-900 text-slate-400 py-6 border-t border-slate-800 text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-slate-300">
              Pulso Eleitoral — Auditoria Técnica e Reproduzível de Urnas TSE
            </p>
            <p className="text-[11px] text-slate-500 mt-1">
              Desenvolvido segundo o protocolo SDD (AI-Native Spec-First). Zero banco relacional em runtime.
            </p>
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <button
              onClick={() => setIsMethodologyOpen(true)}
              className="hover:text-white transition-colors"
            >
              Transparência Metodológica
            </button>
            <span>&bull;</span>
            <a
              href="https://resultados.tse.jus.br"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-white transition-colors"
            >
              Portal TSE Oficial
            </a>
          </div>
        </div>
      </footer>

      {/* Modal de Metodologia */}
      <MethodologyModal
        isOpen={isMethodologyOpen}
        onClose={() => setIsMethodologyOpen(false)}
        metadata={metadata}
      />
    </>
  );
}
