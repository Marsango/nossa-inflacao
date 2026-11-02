import type { DailyComparison, History, LoadState, Observation } from '../data/model';
import type { Period } from '../shared/dates';
import { formatDate, timeZone } from '../shared/dates';
import { chartValue, money, percentage, priceLabel } from '../shared/format';
import { Chart } from './Chart';
import { ShopPrices } from './ShopPrices';
import { availabilityExplanation, variationExplanation, variationStatus } from '../data/availability';

function Summary({ history }: { history: History }) {
  return <div className="summary">
    {history.unit === 'BRL' && <div><span>{priceLabel(history.priceBasis)} · menor disponível na última data com preço</span><strong>{history.latestPriceMinor === null ? 'Indisponível' : money(history.latestPriceMinor)}</strong></div>}
    <div><span>{history.unit === 'BRL' ? 'Variação média entre lojas' : 'Variação média observada'}</span><strong aria-describedby={history.changeBasisPoints === null ? 'variation-explanation' : undefined}>{history.changeBasisPoints === null ? variationStatus(history) : percentage(history.changeBasisPoints)}</strong></div>
    {history.comparisonStart && history.comparisonEnd && <p>{history.unit === 'BRL' ? 'Comparação' : 'Datas dos preços comparados'}: {formatDate(history.comparisonStart)} a {formatDate(history.comparisonEnd)}</p>}
  </div>;
}

function DataTable({ history }: { history: History }) {
  if (history.unit === 'percent') return <OverviewTable history={history} />;
  return <details><summary>Ver dados em tabela</summary><div className="table-scroll"><table>
    <caption>{history.title} — série consolidada</caption>
    <thead><tr><th scope="col">Data</th><th scope="col">{history.unit === 'BRL' ? priceLabel(history.priceBasis) : 'Variação (%)'}</th></tr></thead>
    <tbody>{history.points.map((point) => <tr key={point.date}><td>{formatDate(point.date)}</td>
      <td>{point.value === null ? 'Sem preço comparável' : chartValue(point.value, history.unit)}</td></tr>)}</tbody>
  </table></div></details>;
}

function comparedDate(date?: string | null) { return date ? formatDate(date) : '—'; }

function OverviewRow({ point, comparison, first }: { point: Observation; comparison?: DailyComparison; first: boolean }) {
  return <tr><td>{formatDate(point.date)}</td>
    <td>{first ? 'Base de referência' : point.value === null ? 'Sem comparação disponível' : percentage(point.value)}</td>
    <td>{first ? '—' : comparison?.products ?? 0}</td><td>{first ? '—' : comparison?.shops ?? 0}</td><td>{first ? '—' : comparison?.streams ?? 0}</td>
    <td>{first ? '—' : comparison?.updatedStreams ?? 0}</td>
    <td>{comparedDate(comparison?.comparisonStart)}</td><td>{comparedDate(comparison?.comparisonEnd)}</td>
  </tr>;
}

function OverviewTable({ history }: { history: History }) {
  return <details><summary>Ver dados em tabela</summary>
    <p>A amostra pode mudar a cada dia. Cada contexto conta uma vez, comparando seu primeiro preço positivo com o último preço elegível já observado até a data. Os pares podem cobrir períodos diferentes.</p>
    <p>Comparações históricas continuam incluídas em dias sem novos preços. Isso não confirma o preço nesses dias. Confira as datas realmente comparadas e quantos contextos receberam um novo preço elegível.</p>
    <div className="table-scroll"><table><caption>{history.title} — variações observadas e cobertura por data</caption>
      <thead><tr><th scope="col">Data</th><th scope="col">Variação observada (%)</th><th scope="col">Produtos comparados</th>
        <th scope="col">Lojas</th><th scope="col">Contextos</th><th scope="col">Contextos com novo preço</th>
        <th scope="col">Primeira data comparada</th><th scope="col">Última data comparada</th></tr></thead>
      <tbody>{history.points.map((point, position) => <OverviewRow key={point.date} point={point} first={position === 0 && history.availablePeriod !== null}
        comparison={history.dailyComparisons.find((comparison) => comparison.date === point.date)} />)}</tbody>
    </table></div>
  </details>;
}

function Context({ history }: { history: History }) {
  const collected = history.collectedAt && new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short', timeZone }).format(new Date(history.collectedAt));
  return <div className="context"><p>{history.coverage}</p>
    {history.unknownConditions && <p className="notice" role="status">Condições de compra não informadas em parte das ofertas. São preços anunciados e podem exigir condições não verificadas.</p>}
    <p>{collected ? `Última coleta no período: ${collected} (horário de Brasília).` : 'Sem coleta no período.'}</p>
    <details className="history-methodology"><summary>Metodologia deste histórico</summary>
      <p>{history.methodology}</p><p>Versão: {history.methodologyVersion}</p>
    </details>
    <DataTable history={history} />
  </div>;
}

function HistoryContent({ history, period }: { history: History; period: Period }) {
  const availability = availabilityExplanation(history, period);
  return <>
    {history.stale && <p className="notice" role="status">Dados desatualizados. A última coleta disponível pode não refletir os preços atuais.</p>}
    {history.changeBasisPoints === null && <p className="notice" role="status" id="variation-explanation">{variationExplanation(history)}</p>}
    {history.counts.pricedDays > 0 && <Chart history={history} />}
    {availability && <p className="notice" role="status">{availability}</p>}
    <ShopPrices history={history} />
    <Context history={history} />
  </>;
}

export function HistoryView({ state, period, retry }: { state: LoadState; period: Period; retry: () => void }) {
  if (state.status === 'loading') return <p className="notice" role="status">Carregando histórico…</p>;
  if (state.status === 'error') return <div className="notice" role="alert"><p>Não foi possível carregar o histórico.</p><button onClick={retry}>Tentar novamente</button></div>;
  if (!state.history) return null;
  return <section className="history" aria-labelledby="history-title">
    <div className="history-top"><div className="history-heading"><h2 id="history-title">{state.history.title}</h2>
      <p>{formatDate(period.start)} a {formatDate(period.end)}</p></div><Summary history={state.history} /></div>
    <HistoryContent history={state.history} period={period} />
  </section>;
}
