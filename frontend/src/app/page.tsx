"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Header } from "../components/Header";
import { HeroExecutiveCards } from "../components/HeroExecutiveCards";
import { TabsNav, TabId } from "../components/TabsNav";
import { TimelineTab } from "../components/TimelineTab";
import { GeographyTab } from "../components/GeographyTab";
import { IntegrityTab } from "../components/IntegrityTab";
import { VerdictTab } from "../components/VerdictTab";
import { MethodologyModal } from "../components/MethodologyModal";
import {
  MetadataPayload,
  NationalSummaryPayload,
  TimelinePayload,
  GeographyPayload,
  BiometricsPayload,
  ElectoralImpactPayload,
  LatestSectionsPayload,
} from "../types/audit";
import {
  fetchMetadata,
  fetchNationalSummary,
  fetchTimeline,
  fetchGeography,
  fetchBiometrics,
  fetchElectoralImpact,
  fetchLatestSections,
} from "../lib/api";

export default function HomePage() {
  const [ano, setAno] = useState<number>(2026);
  const [turno, setTurno] = useState<number>(2);
  const [activeTab, setActiveTab] = useState<TabId>("timeline");

  const [metadata, setMetadata] = useState<MetadataPayload | null>(null);
  const [nationalSummary, setNationalSummary] = useState<NationalSummaryPayload | null>(null);
  const [timelineData, setTimelineData] = useState<TimelinePayload | null>(null);
  const [geographyData, setGeographyData] = useState<GeographyPayload | null>(null);
  const [biometricsData, setBiometricsData] = useState<BiometricsPayload | null>(null);
  const [impactData, setImpactData] = useState<ElectoralImpactPayload | null>(null);
  const [sectionsData, setSectionsData] = useState<LatestSectionsPayload | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [isMethodologyOpen, setIsMethodologyOpen] = useState<boolean>(false);

  // Carrega datasets analíticos ao selecionar pleito/turno
  const loadDashboardData = useCallback(async (year: number, round: number) => {
    setLoading(true);
    try {
      const [meta, nat, time, geo, bio, impact, sec] = await Promise.all([
        fetchMetadata(year, round),
        fetchNationalSummary(year, round),
        fetchTimeline(year, round),
        fetchGeography(year, round),
        fetchBiometrics(year, round),
        fetchElectoralImpact(year, round),
        fetchLatestSections(year, round),
      ]);
      setMetadata(meta);
      setNationalSummary(nat);
      setTimelineData(time);
      setGeographyData(geo);
      setBiometricsData(bio);
      setImpactData(impact);
      setSectionsData(sec);
    } catch (err) {
      console.error("Erro ao carregar dados analíticos do Pulso Eleitoral:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData(ano, turno);
  }, [ano, turno, loadDashboardData]);

  const handleSelectElection = (newAno: number, newTurno: number) => {
    setAno(newAno);
    setTurno(newTurno);
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

      <main id="main-content" className="flex-1 max-w-[1280px] mx-auto px-4 sm:px-6 py-5 w-full">
        {/* 1. Hero Executive Story Cards */}
        <HeroExecutiveCards
          summary={nationalSummary}
          ano={ano}
          turno={turno}
          loading={loading}
        />

        {/* 2. Navegação em Abas Narrativas Científicas */}
        <TabsNav activeTab={activeTab} onTabChange={setActiveTab} />

        {/* 3. Renderização Dinâmica dos 4 Atos */}
        <div className="pb-8">
          {activeTab === "timeline" && (
            <TimelineTab data={timelineData} loading={loading} />
          )}

          {activeTab === "geography" && (
            <GeographyTab data={geographyData} loading={loading} />
          )}

          {activeTab === "integrity" && (
            <IntegrityTab data={biometricsData} loading={loading} />
          )}

          {activeTab === "verdict" && (
            <VerdictTab
              impactData={impactData}
              sectionsData={sectionsData}
              ano={ano}
              loading={loading}
            />
          )}
        </div>
      </main>

      {/* 4. Rodapé Institucional idêntico ao Streamlit */}
      <footer className="text-center text-[#64748B] text-xs py-8 border-t border-[#1E242C] mt-8 bg-[#121417]">
        <div className="max-w-[1280px] mx-auto px-4 space-y-1">
          <div>
            <strong className="text-[#94A3B8]">Pulso Eleitoral</strong> &bull; Auditoria de Logs de Urna TSE.
          </div>
          <div>
            Dados abertos oficiais do Tribunal Superior Eleitoral (TSE). Horários normalizados para o Horário de Brasília (BRT / UTC-3).
          </div>
        </div>
      </footer>

      {/* Modal de Transparência Metodológica */}
      <MethodologyModal
        isOpen={isMethodologyOpen}
        onClose={() => setIsMethodologyOpen(false)}
        metadata={metadata}
      />
    </>
  );
}
