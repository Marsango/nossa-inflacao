import type { History } from './model';
import { formatDate, type Period } from '../shared/dates';

export function availabilityExplanation(history: History, selected: Period) {
  const available = history.availablePeriod;
  if (!available || (available.start === selected.start && available.end === selected.end)) return null;
  if (available.start === available.end) return `Neste período, há preços disponíveis apenas em ${formatDate(available.start)}. Não há dados para calcular uma variação.`;
  const comparison = history.comparisonStart && history.comparisonEnd === available.end ? ' A comparação usa essas datas.' : '';
  const gaps = history.unit === 'percent' ? ' A visão geral conserva comparações históricas já conhecidas; confira as datas na tabela.' : ' Dias sem preço permanecem como lacunas.';
  return `Neste período, há preços disponíveis apenas entre ${formatDate(available.start)} e ${formatDate(available.end)}.${comparison}${gaps}`;
}

export function chartCaption(history: History) {
  if (history.unit === 'percent' && history.points.length === 1) return 'Base de referência (%) · Variação não calculável';
  if (history.unit === 'percent') return 'Média das variações observadas até cada data (%)';
  if (history.counts.includedStreams === 0) return 'Menor preço disponível por dia · As lojas e os contextos podem variar; esta série não calcula variação';
  return 'Média do painel comparável';
}

export function variationStatus(history: History) {
  if (history.counts.pricedDays === 0) return 'Sem dias comparáveis';
  if (history.counts.pricedDays === 1) return 'Histórico insuficiente';
  return 'Não calculável';
}

export function variationExplanation(history: History) {
  const available = history.availablePeriod;
  if (history.counts.products === 0) return 'Nenhum preço disponível neste período. Escolha outro intervalo ou produto.';
  if (!available) return 'Nenhum preço elegível neste período. Preços ausentes e condições ou embalagens incompatíveis ficam fora da comparação. Escolha outro intervalo ou produto.';
  if (available.start === available.end) return 'Há preços disponíveis em apenas um dia. A variação precisa de pelo menos dois dias no período. Amplie o período ou aguarde novas coletas.';
  if (history.unit === 'percent') return overviewExplanation(history);
  if (history.counts.includedStreams === 0 && history.unit === 'BRL') return 'Não há preços comparáveis nas duas datas com dados. O gráfico mostra os menores preços disponíveis por dia, que podem vir de lojas ou contextos diferentes. Esses valores não permitem calcular uma variação comparável.';
  if (history.counts.pricedDays === 1) return 'Há preços comparáveis em apenas um dia. A variação precisa de pelo menos dois dias no período. Amplie o período ou aguarde novas coletas.';
  if (history.counts.pricedDays > 1) return 'Não foi possível calcular a variação com os preços disponíveis. A comparação exige os mesmos contextos nas duas datas com dados, uma base positiva e um resultado representável.';
  return 'Não foi possível calcular a variação comparável. Consulte os preços disponíveis por loja ou escolha outro intervalo. Preços ausentes e condições ou embalagens incompatíveis ficam fora da comparação.';
}

function overviewExplanation(history: History) {
  if (history.counts.includedStreams === 0) return 'Ainda não há dois preços elegíveis em datas distintas no mesmo contexto de compra neste período. As datas não precisam ser consecutivas. Busque um produto para ver os preços disponíveis.';
  return 'Não foi possível representar a média das variações observadas com os preços disponíveis. Consulte as datas e a cobertura das comparações na tabela ou escolha outro intervalo.';
}
