/**
 * Tipagens TypeScript canônicas do Pulso Eleitoral (TSE Audit Pipeline).
 * Espelham rigorosamente os contratos Pydantic v2 e JSON Schema Draft 2020-12.
 */

export interface OutlierThresholds {
  min_votos_pos_17h: number;
  delta_sem_bio_pp: number;
  z_score_uf: number;
}

export interface MetadataPayload {
  schema_version: string;
  pipeline_version: string;
  ano_eleicao: number;
  turno: number;
  pleito_id: number;
  cutoff_mode: string;
  generated_at: string;
  duckdb_sha256: string;
  outlier_thresholds: OutlierThresholds;
}

export interface FlaggedCountsByTier {
  TIER_3_CRITICAL_ANOMALY: number;
  TIER_2_STATISTICAL_OUTLIER: number;
  TIER_1_POST_17H_NO_BIO: number;
}

export interface NationalSummaryPayload {
  ano_eleicao: number;
  turno: number;
  total_secoes_manifesto: number;
  total_secoes_analisadas: number;
  total_secoes_nao_processadas: number;
  cobertura_secoes_pct: number;
  total_aptos_brasil: number;
  total_votos_brasil: number;
  votos_ate_17h_brasil: number;
  votos_apos_17h_brasil: number;
  sem_bio_ate_17h_brasil: number;
  sem_bio_apos_17h_brasil: number;
  pct_apos_17h: number;
  pct_sem_bio_ate_17h: number;
  pct_sem_bio_apos_17h: number;
  flagged_counts_by_tier: FlaggedCountsByTier;
}

export interface StateSummaryItem {
  uf: string;
  total_secoes_manifesto: number;
  total_secoes_analisadas: number;
  total_secoes_nao_processadas: number;
  total_votos: number;
  votos_ate_17h: number;
  votos_apos_17h: number;
  sem_bio_ate_17h: number;
  sem_bio_apos_17h: number;
  pct_votos_apos_17h: number;
  pct_sem_bio_ate_17h: number;
  pct_sem_bio_apos_17h: number;
  uf_mean_sem_bio_pos_17h: number;
  uf_std_sem_bio_pos_17h: number;
  tier_2_outliers_count: number;
  tier_3_anomalies_count: number;
}

export interface StatesSummaryPayload {
  ano_eleicao: number;
  turno: number;
  states: StateSummaryItem[];
}

export interface MunicipalitySummaryItem {
  municipio_cod: number;
  municipio_ibge: number | null;
  municipio_nome: string;
  fuso_horario_offset_brt: number;
  total_secoes_manifesto: number;
  total_secoes_analisadas: number;
  total_secoes_nao_processadas: number;
  total_aptos: number;
  total_votos: number;
  votos_ate_17h: number;
  votos_apos_17h: number;
  sem_bio_ate_17h: number;
  sem_bio_apos_17h: number;
  pct_votos_apos_17h: number;
  pct_sem_bio_ate_17h: number;
  pct_sem_bio_apos_17h: number;
}

export interface MunicipalitiesPayload {
  ano_eleicao: number;
  turno: number;
  uf: string;
  municipalities: MunicipalitySummaryItem[];
}

export interface FlaggedSectionItem {
  uf: string;
  municipio_cod: number;
  municipio_nome: string;
  zona: number;
  secao: number;
  fuso_horario_offset_brt: number;
  total_aptos: number | null;
  total_votos: number;
  votos_ate_17h: number;
  votos_apos_17h: number;
  sem_bio_ate_17h: number;
  sem_bio_apos_17h: number;
  pct_votos_apos_17h: number;
  pct_sem_bio_ate_17h: number;
  pct_sem_bio_apos_17h: number;
  delta_sem_bio_pp: number;
  z_score_uf_pos_17h: number;
  divergencia_bu_log: number | null;
  relogio_suspeito: boolean;
  voto_apos_encerramento: boolean;
  horario_ultimo_voto_brt: string | null;
  severidade_sinalizacao: string;
}

export interface FlaggedSectionsPayload {
  ano_eleicao: number;
  turno: number;
  scope: string;
  total_matching_sections: number;
  returned_sections: number;
  items: FlaggedSectionItem[];
}
