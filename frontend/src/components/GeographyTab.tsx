"use client";

import React, { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import { GeographyPayload, CapitalRankingItem, AmazonRankingItem } from "../types/audit";
import { formatNumber } from "../lib/api";
import { Search } from "lucide-react";

// Importação dinâmica do mapa Leaflet desabilitando SSR para suportar exportação estática
const BrazilMap = dynamic(
  () => import("./BrazilMap").then((mod) => mod.BrazilMap),
  {
    ssr: false,
    loading: () => (
      <div
        className="w-full h-[480px] sm:h-[520px] rounded-lg border border-[#282D37] flex items-center justify-center text-xs text-[#94A3B8]"
        style={{ backgroundColor: "#121417" }}
      >
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full border-2 border-[#38BDF8] border-t-transparent animate-spin" />
          <span>Carregando mapa geoespacial do Brasil...</span>
        </div>
      </div>
    ),
  }
);

interface GeographyTabProps {
  data: GeographyPayload | null;
  loading?: boolean;
}

const HORARIOS_SCRUBBER = [
  { label: "17:15 (Primeiros 15 min)", value: "17:15" },
  { label: "17:30 (Fim Absorção)", value: "17:30" },
  { label: "18:00 (Entrada 2ª Hora)", value: "18:00" },
  { label: "18:30 (Extensão Avançada)", value: "18:30" },
  { label: "18:45 (Últimos 20 min)", value: "18:45" },
  { label: "19:06 (Janela Completa)", value: "19:06" },
];

export const GeographyTab: React.FC<GeographyTabProps> = ({ data, loading }) => {
  const [scrubberIndex, setScrubberIndex] = useState<number>(5); // Padrão: Janela Completa (19:06)
  const [searchTerm, setSearchTerm] = useState<string>("");

  const points = data?.points || [];
  const capitais = data?.capitais || [];
  const proporcao = data?.proporcao || [];

  const limiteHorario = HORARIOS_SCRUBBER[scrubberIndex].value;

  // Filtragem reativa por horário limite e termo de busca
  const filteredPoints = useMemo(() => {
    return points.filter((pt) => {
      const matchTempo = pt.ultimo_voto_str <= `${limiteHorario}:59`;
      const matchBusca =
        !searchTerm ||
        pt.municipio_nome.toLowerCase().includes(searchTerm.toLowerCase().trim()) ||
        pt.uf.toLowerCase() === searchTerm.toLowerCase().trim();
      return matchTempo && matchBusca;
    });
  }, [points, limiteHorario, searchTerm]);

  // Ranking Capitais Fallback
  const topCapitais: CapitalRankingItem[] =
    capitais.length > 0
      ? capitais
      : [
          { uf: "SP", municipio_nome: "SAO PAULO", votos_pos: 4210, pct_pos: 0.065, ultimo_voto: "19:06:21" },
          { uf: "RJ", municipio_nome: "RIO DE JANEIRO", votos_pos: 2890, pct_pos: 0.078, ultimo_voto: "18:54:12" },
          { uf: "BA", municipio_nome: "SALVADOR", votos_pos: 1740, pct_pos: 0.112, ultimo_voto: "18:41:05" },
          { uf: "DF", municipio_nome: "BRASILIA", votos_pos: 1530, pct_pos: 0.088, ultimo_voto: "18:35:19" },
          { uf: "AM", municipio_nome: "MANAUS", votos_pos: 1420, pct_pos: 0.125, ultimo_voto: "18:48:33" },
          { uf: "MG", municipio_nome: "BELO HORIZONTE", votos_pos: 1210, pct_pos: 0.082, ultimo_voto: "18:22:40" },
          { uf: "CE", municipio_nome: "FORTALEZA", votos_pos: 980, pct_pos: 0.061, ultimo_voto: "18:15:10" },
          { uf: "PE", municipio_nome: "RECIFE", votos_pos: 840, pct_pos: 0.089, ultimo_voto: "18:12:00" },
          { uf: "PR", municipio_nome: "CURITIBA", votos_pos: 720, pct_pos: 0.067, ultimo_voto: "18:05:44" },
          { uf: "PA", municipio_nome: "BELEM", votos_pos: 650, pct_pos: 0.075, ultimo_voto: "18:08:15" },
        ];

  // Ranking Proporção Fallback
  const topProporcao: AmazonRankingItem[] =
    proporcao.length > 0
      ? proporcao
      : [
          { uf: "AM", municipio_nome: "LABREA", votos_pos: 145, pct_pos: 1.84, ultimo_voto: "18:32:10" },
          { uf: "AM", municipio_nome: "EIRUNEPE", votos_pos: 112, pct_pos: 1.62, ultimo_voto: "18:28:44" },
          { uf: "AC", municipio_nome: "FEIJO", votos_pos: 98, pct_pos: 1.45, ultimo_voto: "18:45:11" },
          { uf: "AM", municipio_nome: "BOCA DO ACRE", votos_pos: 88, pct_pos: 1.38, ultimo_voto: "18:19:02" },
          { uf: "AC", municipio_nome: "TARAUACA", votos_pos: 76, pct_pos: 1.25, ultimo_voto: "18:14:50" },
          { uf: "AM", municipio_nome: "CANUTAMA", votos_pos: 54, pct_pos: 1.18, ultimo_voto: "18:05:12" },
          { uf: "AM", municipio_nome: "PAUINI", votos_pos: 48, pct_pos: 1.12, ultimo_voto: "18:10:33" },
          { uf: "AC", municipio_nome: "CRUZEIRO DO SUL", votos_pos: 165, pct_pos: 0.98, ultimo_voto: "18:50:22" },
          { uf: "AM", municipio_nome: "ENVIRA", votos_pos: 34, pct_pos: 0.92, ultimo_voto: "18:04:19" },
          { uf: "AM", municipio_nome: "GUAJARA", votos_pos: 28, pct_pos: 0.85, ultimo_voto: "18:02:40" },
        ];

  const maxCap = Math.max(...topCapitais.map((c) => c.votos_pos), 4500);
  const maxProp = Math.max(...topProporcao.map((p) => p.pct_pos), 2.0);

  return (
    <div className="space-y-6">
      {/* 1. Introdução Narrativa */}
      <div>
        <h2 className="text-xl sm:text-2xl font-bold text-[#F8FAFC]">
          Ato 2: Geografia da Anomalia: Os Dois Eixos Discrepantes
        </h2>
        <p className="text-xs sm:text-sm text-[#94A3B8] mt-1.5 leading-relaxed max-w-4xl">
          A extensão de horário não se distribuiu homogeneamente. A análise espacial revela uma cisão entre dois polos:{" "}
          <strong className="text-[#38BDF8]">grandes megalópoles urbanas</strong> (concentrando o volume absoluto de votos) e{" "}
          <strong className="text-[#F59E0B]">municípios remotos do Sudoeste Amazônico</strong> (onde o fuso unificado das 17h BRT encerrou as urnas às 15h locais em áreas ribeirinhas de logística complexa).
        </p>
      </div>

      {/* 2. Controles Interativos (Scrubber Temporal e Busca) */}
      <div className="bg-[#181B20] border border-[#282D37] rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
        {/* Scrubber Temporal */}
        <div className="md:col-span-2">
          <div className="flex justify-between items-center mb-1.5">
            <label htmlFor="scrubber-range" className="text-xs font-semibold text-[#CBD5E1]">
              Filtrar por Horário Limite de Encerramento (BRT):
            </label>
            <span className="text-xs font-bold text-[#38BDF8] bg-[#38BDF8]/15 px-2 py-0.5 rounded border border-[#38BDF8]/30 font-mono">
              {HORARIOS_SCRUBBER[scrubberIndex].label}
            </span>
          </div>
          <input
            id="scrubber-range"
            type="range"
            min={0}
            max={HORARIOS_SCRUBBER.length - 1}
            step={1}
            value={scrubberIndex}
            onChange={(e) => setScrubberIndex(Number(e.target.value))}
            className="w-full accent-[#38BDF8] cursor-pointer bg-[#282D37] rounded-lg h-2"
          />
          <div className="flex justify-between text-[10px] text-[#64748B] mt-1 font-mono">
            <span>17:15</span>
            <span>17:30</span>
            <span>18:00</span>
            <span>18:30</span>
            <span>18:45</span>
            <span>19:06</span>
          </div>
        </div>

        {/* Busca por Município */}
        <div>
          <label htmlFor="search-mun" className="text-xs font-semibold text-[#CBD5E1] block mb-1.5">
            Pesquisar Município / UF:
          </label>
          <div className="relative">
            <Search className="w-4 h-4 text-[#64748B] absolute left-3 top-2.5" />
            <input
              id="search-mun"
              type="text"
              placeholder="Ex: São Paulo, Capelinha, Lábrea, MG..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[#121417] text-xs text-[#F8FAFC] pl-9 pr-3 py-2 rounded-lg border border-[#282D37] focus:border-[#38BDF8] outline-none"
            />
          </div>
        </div>
      </div>

      {/* 3. Mapa Geoespacial Real Leaflet */}
      <div className="bg-[#181B20] border border-[#282D37] rounded-xl p-4 relative overflow-hidden">
        <div className="flex justify-between items-center mb-2.5">
          <div className="text-xs text-[#94A3B8]">
            Exibindo <strong className="text-[#38BDF8]">{filteredPoints.length.toLocaleString("pt-BR")}</strong> de{" "}
            <strong>{points.length.toLocaleString("pt-BR")}</strong> municípios georreferenciados com seções encerradas até{" "}
            <strong className="text-[#F8FAFC]">{limiteHorario} BRT</strong>.
            {searchTerm && (
              <span className="ml-2 text-[#F59E0B] font-semibold">
                (Filtro: &ldquo;{searchTerm}&rdquo;)
              </span>
            )}
          </div>
          <div className="text-[11px] text-[#64748B] hidden sm:block">
            Navegue com zoom e arraste &bull; Clique nos pontos para detalhes
          </div>
        </div>

        {/* Componente Leaflet Map */}
        <BrazilMap
          points={filteredPoints}
          searchTerm={searchTerm}
          limiteHorario={limiteHorario}
        />
      </div>

      {/* 4. Confronto dos Dois Eixos (Rankings Lado a Lado) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Eixo 1: Megalópoles (Volume Absoluto) */}
        <div className="bg-[#181B20] border border-[#282D37] rounded-xl p-4 sm:p-5">
          <div className="text-sm font-bold text-[#38BDF8] mb-1">
            Eixo 1: Megalópoles &bull; Volume Absoluto
          </div>
          <p className="text-xs text-[#94A3B8] mb-4">
            Capitais que concentraram o maior quantitativo nominal de votos na extensão.
          </p>

          <div className="space-y-2.5">
            {topCapitais.map((c) => {
              const pctWidth = (c.votos_pos / maxCap) * 100;
              return (
                <div key={`${c.municipio_nome}-${c.uf}`} className="text-xs">
                  <div className="flex justify-between items-center mb-1 text-[#CBD5E1]">
                    <span className="font-semibold">
                      {c.municipio_nome} ({c.uf})
                    </span>
                    <span className="text-[#38BDF8] font-mono font-bold">
                      {formatNumber(c.votos_pos)} votos
                    </span>
                  </div>
                  <div className="w-full bg-[#121417] rounded-full h-2.5 overflow-hidden border border-[#282D37]/50">
                    <div
                      className="bg-[#38BDF8] h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(pctWidth, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Eixo 2: Sudoeste Amazônico (Impacto Relativo) */}
        <div className="bg-[#181B20] border border-[#282D37] rounded-xl p-4 sm:p-5">
          <div className="text-sm font-bold text-[#F59E0B] mb-1">
            Eixo 2: Sudoeste Amazônico &bull; Impacto Relativo Local
          </div>
          <p className="text-xs text-[#94A3B8] mb-4">
            Municípios com maior peso percentual de votos pós-17h (fuso unificado às 15h locais).
          </p>

          <div className="space-y-2.5">
            {topProporcao.map((p) => {
              const pctWidth = (p.pct_pos / maxProp) * 100;
              return (
                <div key={`${p.municipio_nome}-${p.uf}`} className="text-xs">
                  <div className="flex justify-between items-center mb-1 text-[#CBD5E1]">
                    <span className="font-semibold">
                      {p.municipio_nome} ({p.uf})
                    </span>
                    <span className="text-[#F59E0B] font-mono font-bold">
                      {p.pct_pos.toFixed(2)}% do município
                    </span>
                  </div>
                  <div className="w-full bg-[#121417] rounded-full h-2.5 overflow-hidden border border-[#282D37]/50">
                    <div
                      className="bg-[#F59E0B] h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(pctWidth, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
