# Especificação 06: Teste Paramétrico e Limites Determinísticos de Impacto Eleitoral

**Agente Responsável:** `agent-analytics` (`src/pulso_eleitoral/analytics/`)  
**Requisito Coberto:** `REQ-ANA-03`

---

## 1. Fundamentação Matemática e Teórica

### 1.1. Limites Extremos de Causalidade (Bounds de Manski)
Seja $V_A$ o total de votos válidos do Candidato A e $V_B$ o total do Candidato B no resultado eleitoral oficial, com uma margem de vitória absoluta:
$$\Delta_{\text{oficial}} = |V_A - V_B|$$

Seja $V_{\text{pós-17h}} = \sum_{s=1}^S v_{\text{pós-17h}, s}$ o número agregado de votos confirmados na janela após o horário oficial de encerramento das 17:00:00 (BRT) em todo o território nacional.

#### Teorema da Invariância Determinística do Resultado:
Se a margem de vitória do candidato vencedor for estritamente superior ao volume total de votos registrados na janela estendida:
$$\Delta_{\text{oficial}} > V_{\text{pós-17h}} \implies \mathbb{P}(\text{Inversão de Resultado}) = 0$$

*Demonstração:*
No cenário contrafactual extremo de maior viés possível ($\mathcal{C}_{\text{extremo}}$), assume-se que 100% dos votos de $V_{\text{pós-17h}}$ foram atribuídos ao candidato vencedor e zero ao derrotado. A remoção contrafactual dessa janela produziria uma nova margem:
$$\Delta_{\text{contrafactual}} = \Delta_{\text{oficial}} - V_{\text{pós-17h}}$$
Como $\Delta_{\text{oficial}} > V_{\text{pós-17h}}$, segue que $\Delta_{\text{contrafactual}} > 0$, mantendo a ordem estrita dos concorrentes e a invariância do vencedor da eleição.

---

### 1.2. Modelo Econométrico de Regressão com Efeitos Fixos Municipais (Within-Estimator)
Para testar se a extensão de horário favoreceu ou prejudicou o Candidato A ou B nas seções eleitorais onde ela ocorreu:

Seja $s$ o índice da seção eleitoral e $m$ o índice do município ($s \in \{1, \dots, S_m\}$, $m \in \{1, \dots, M\}$).

$$Y_{sm} = \alpha_m + \beta_1 X_{1, sm} + \beta_2 X_{2, sm} + \gamma \ln(\text{total\_votos}_{sm}) + \varepsilon_{sm}$$

Onde:
- $Y_{sm}$: Proporção de votos nominais válidos do Candidato A na seção $s$ do município $m$.
- $\alpha_m$: Efeito fixo do município $m$ (absorve idiossincrasias sociodemográficas, regionais e geográficas).
- $X_{1, sm} = \frac{v_{\text{pós-17h}, sm}}{\text{total\_votos}_{sm}}$: Proporção de votos pós-17h da seção.
- $X_{2, sm} = \frac{\text{sem\_bio\_pós-17h}, sm}{v_{\text{pós-17h}, sm}}$: Proporção de votos sem biometria na janela estendida.
- $\varepsilon_{sm}$: Termo de erro idiossincrático com esperança condicional zero.

#### Transformação Within:
Subtraindo a média municipal de cada variável ($\tilde{Z}_{sm} = Z_{sm} - \bar{Z}_m$):
$$\tilde{Y}_{sm} = \beta_1 \tilde{X}_{1, sm} + \beta_2 \tilde{X}_{2, sm} + \gamma \widetilde{\ln(\text{total\_votos}_{sm})} + \tilde{\varepsilon}_{sm}$$

O estimador de Mínimos Quadrados Ordinários / Ponderados (WLS ponderado por $\text{total\_votos}_{sm}$) é:
$$\hat{\boldsymbol{\beta}} = (\tilde{\mathbf{X}}' \mathbf{W} \tilde{\mathbf{X}})^{-1} \tilde{\mathbf{X}}' \mathbf{W} \tilde{\mathbf{Y}}$$

#### Erros-Padrão Clusterizados no Nível de Município (CRVE):
Como seções do mesmo município compartilham correlação intra-cluster:
$$\mathbb{V}_{\text{cluster}}(\hat{\boldsymbol{\beta}}) = (\tilde{\mathbf{X}}' \mathbf{W} \tilde{\mathbf{X}})^{-1} \left( \sum_{m=1}^M \tilde{\mathbf{X}}_m' \mathbf{W}_m \mathbf{e}_m \mathbf{e}_m' \mathbf{W}_m \tilde{\mathbf{X}}_m \right) (\tilde{\mathbf{X}}' \mathbf{W} \tilde{\mathbf{X}})^{-1}$$

---

### 1.3. Testes Paramétricos de Hipótese
1. **Teste de Neutralidade Eleitoral da Extensão ($t$ de Student):**
   - $H_0: \beta_1 = 0$ (a proporção de votos pós-17h não possui associação estatística com o desempenho de A ou B).
   - $H_1: \beta_1 \neq 0$ (associação estatisticamente significante com viés partidário/candidato).
   - Estatística de teste:
     $$t = \frac{\hat{\beta}_1 - 0}{\text{SE}_{\text{cluster}}(\hat{\beta}_1)}$$
   - $p$-valor bicaudal: $p = 2 \cdot (1 - \Phi_t(|t|, \text{df}=M - K))$.
2. **Estimativa de Deslocamento Líquido Contrafactual de Votos:**
   $$\hat{\Delta}_{\text{votos}, A} = \sum_{s=1}^S \hat{\beta}_1 \cdot v_{\text{pós-17h}, s}$$
   com intervalo de confiança paramétrico de 95%:
   $$\text{IC}_{95\%} = \left[ (\hat{\beta}_1 - 1{,}96 \cdot \text{SE}) \sum v_{\text{pós-17h}, s}, \; (\hat{\beta}_1 + 1{,}96 \cdot \text{SE}) \sum v_{\text{pós-17h}, s} \right]$$

---

## 2. Contratos Python e Saída Estruturada

O módulo `src/pulso_eleitoral/analytics/electoral_impact.py` deve expor:
1. `calculate_manski_bounds(...) -> SensitivityBoundsResult`
2. `run_parametric_bias_model(...) -> ParametricRegressionResult`
3. `generate_electoral_impact_report(...) -> ElectoralImpactReport`

Todos os modelos de retorno devem ser definidos em `src/pulso_eleitoral/contracts/models.py`.
