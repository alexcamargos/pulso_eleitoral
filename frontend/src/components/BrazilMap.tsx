"use client";

import React, { useEffect, useRef } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import { GeographyPointItem } from "../types/audit";
import { formatNumber } from "../lib/api";

interface BrazilMapProps {
  points: GeographyPointItem[];
  searchTerm: string;
  limiteHorario: string;
}

export const BrazilMap: React.FC<BrazilMapProps> = ({
  points,
  searchTerm,
  limiteHorario,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<LeafletMap | null>(null);
  const markersLayerRef = useRef<LayerGroup | null>(null);
  const isInitialMount = useRef<boolean>(true);

  // Inicializa o mapa Leaflet
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    let isSubscribed = true;

    import("leaflet").then((L) => {
      if (!isSubscribed || !mapContainerRef.current) return;

      // Cria a instância do mapa centrada no Brasil
      const map = L.map(mapContainerRef.current, {
        center: [-14.5, -53.5],
        zoom: 4,
        minZoom: 3,
        maxZoom: 16,
        zoomControl: true,
        attributionControl: true,
      });

      // Basemap Dark Matter (CARTO / OpenStreetMap) - alta fidelidade ao Streamlit
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 19,
      }).addTo(map);

      const markersGroup = L.layerGroup().addTo(map);
      markersLayerRef.current = markersGroup;
      mapInstanceRef.current = map;

      // Invalida o tamanho após o primeiro frame para evitar tiles cinzas
      setTimeout(() => {
        map.invalidateSize();
      }, 200);
    });

    return () => {
      isSubscribed = false;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markersLayerRef.current = null;
      }
    };
  }, []);

  // Atualiza os marcadores e a posição da câmera quando os pontos ou filtros mudam
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    if (!map || !markersGroup) return;

    import("leaflet").then((L) => {
      markersGroup.clearLayers();

      const canvasRenderer = L.canvas({ padding: 0.5 });
      let singleMatchMarker: ReturnType<typeof L.circleMarker> | null = null;

      points.forEach((pt) => {
        if (!pt.latitude || !pt.longitude) return;

        // Raio calibrado para visibilidade balanceada sem saturar
        const radius = Math.min(
          Math.max(3.5, 2.5 + Math.log2(pt.votos_pos + 1) * 1.3),
          20
        );

        const isExactMatch =
          searchTerm.trim().length > 0 &&
          (pt.municipio_nome.toLowerCase().includes(searchTerm.toLowerCase().trim()) ||
            pt.uf.toLowerCase() === searchTerm.toLowerCase().trim());

        const marker = L.circleMarker([pt.latitude, pt.longitude], {
          renderer: canvasRenderer,
          radius: isExactMatch ? Math.max(radius, 7) : radius,
          fillColor: isExactMatch ? "#F59E0B" : "#38BDF8",
          fillOpacity: isExactMatch ? 0.95 : 0.65,
          color: isExactMatch ? "#F8FAFC" : "#0284C7",
          weight: isExactMatch ? 2 : 1,
        });

        const popupContent = `
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12.5px;">
            <div style="font-weight: 800; color: #F8FAFC; font-size: 13.5px; margin-bottom: 2px;">
              ${pt.municipio_nome} - ${pt.uf}
            </div>
            <hr style="border: 0; border-top: 1px solid #282D37; margin: 5px 0 7px 0;" />
            <div style="color: #94A3B8; margin-bottom: 3px;">
              Votos pós-17h: <b style="color: #38BDF8;">${formatNumber(pt.votos_pos)}</b>
            </div>
            <div style="color: #94A3B8; margin-bottom: 3px;">
              Fatia do município: <b style="color: #CBD5E1;">${pt.pct_apos_17h.toFixed(3)}%</b>
            </div>
            <div style="color: #94A3B8;">
              Último voto: <b style="color: #F8FAFC; font-family: monospace;">${pt.ultimo_voto_str} BRT</b>
            </div>
          </div>
        `;

        marker.bindPopup(popupContent, {
          closeButton: true,
          className: "dark-custom-popup",
        });

        markersGroup.addLayer(marker);

        if (isExactMatch && !singleMatchMarker) {
          singleMatchMarker = marker;
        }
      });

      // Comportamento inteligente de câmera:
      // Se houver busca e poucos resultados, dá flyTo / fitBounds com zoom no local!
      const trimmedSearch = searchTerm.trim().toLowerCase();
      if (trimmedSearch.length >= 2) {
        if (points.length === 1) {
          const single = points[0];
          map.flyTo([single.latitude, single.longitude], 11, {
            duration: 1.2,
          });
          if (singleMatchMarker) {
            setTimeout(() => {
              singleMatchMarker?.openPopup();
            }, 1250);
          }
        } else if (points.length > 1 && points.length <= 15) {
          const latLngs = points.map((p) => [p.latitude, p.longitude] as [number, number]);
          const bounds = L.latLngBounds(latLngs);
          map.fitBounds(bounds, {
            padding: [50, 50],
            maxZoom: 10,
            duration: 1.0,
          });
        }
      } else if (!isInitialMount.current && trimmedSearch.length === 0) {
        // Quando a busca for limpa, retorna à visão geral do Brasil
        map.flyTo([-14.5, -53.5], 4, {
          duration: 1.0,
        });
      }

      isInitialMount.current = false;
    });
  }, [points, searchTerm, limiteHorario]);

  return (
    <div
      ref={mapContainerRef}
      className="w-full h-[480px] sm:h-[520px] rounded-lg border border-[#282D37] z-10 overflow-hidden"
      style={{ backgroundColor: "#121417" }}
    />
  );
};
