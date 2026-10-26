import {
  MetadataPayload,
  NationalSummaryPayload,
  StatesSummaryPayload,
  MunicipalitiesPayload,
  FlaggedSectionsPayload,
} from "../types/audit";

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

export function getApiBaseUrl(ano: number = 2022, turno: number = 1): string {
  return `${BASE_PATH}/api/v1/ele${ano}/turno${turno}`;
}

export async function fetchMetadata(
  ano: number = 2022,
  turno: number = 1
): Promise<MetadataPayload | null> {
  try {
    const res = await fetch(`${getApiBaseUrl(ano, turno)}/metadata.json`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error("Falha ao carregar metadata.json:", err);
    return null;
  }
}

export async function fetchNationalSummary(
  ano: number = 2022,
  turno: number = 1
): Promise<NationalSummaryPayload | null> {
  try {
    const res = await fetch(`${getApiBaseUrl(ano, turno)}/national_summary.json`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error("Falha ao carregar national_summary.json:", err);
    return null;
  }
}

export async function fetchStatesSummary(
  ano: number = 2022,
  turno: number = 1
): Promise<StatesSummaryPayload | null> {
  try {
    const res = await fetch(`${getApiBaseUrl(ano, turno)}/states_summary.json`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error("Falha ao carregar states_summary.json:", err);
    return null;
  }
}

export async function fetchMunicipalities(
  uf: string,
  ano: number = 2022,
  turno: number = 1
): Promise<MunicipalitiesPayload | null> {
  try {
    const res = await fetch(
      `${getApiBaseUrl(ano, turno)}/municipalities/${uf.toUpperCase()}.json`
    );
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error(`Falha ao carregar municipalities/${uf}.json:`, err);
    return null;
  }
}

export async function fetchFlaggedSections(
  uf?: string,
  ano: number = 2022,
  turno: number = 1
): Promise<FlaggedSectionsPayload | null> {
  try {
    const path = uf
      ? `${getApiBaseUrl(ano, turno)}/flagged_sections/${uf.toUpperCase()}.json`
      : `${getApiBaseUrl(ano, turno)}/flagged_sections/index.json`;
    const res = await fetch(path);
    if (!res.ok) {
      // Fallback para flagged_sections.json na raiz se index.json não responder
      if (!uf) {
        const fallbackRes = await fetch(`${getApiBaseUrl(ano, turno)}/flagged_sections.json`);
        if (fallbackRes.ok) return await fallbackRes.json();
      }
      return null;
    }
    return await res.json();
  } catch (err) {
    console.error("Falha ao carregar flagged_sections:", err);
    return null;
  }
}

export function formatNumber(val: number | null | undefined): string {
  if (val === null || val === undefined) return "—";
  return new Intl.NumberFormat("pt-BR").format(val);
}

export function formatPercent(val: number | null | undefined): string {
  if (val === null || val === undefined) return "—";
  return `${val.toFixed(2).replace(".", ",")}%`;
}

export function getTseResultUrl(
  ano: number,
  uf: string,
  municipioCod: number,
  zona: number,
  secao: number
): string {
  const ufLower = uf.toLowerCase();
  const munStr = String(municipioCod).padStart(5, "0");
  const zonaStr = String(zona).padStart(4, "0");
  const secaoStr = String(secao).padStart(4, "0");
  return `https://resultados.tse.jus.br/oficial/#/eleicao/ele${ano}/detalhe-da-secao/${ufLower}/${munStr}/${zonaStr}/${secaoStr}`;
}
