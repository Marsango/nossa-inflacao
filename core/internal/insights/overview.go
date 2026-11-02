package insights

import (
	"fmt"
	"math/big"
	"sort"
	"strings"
	"time"
)

const overviewMethodology = "A visão geral mostra a média das variações já observadas até cada data, no horário de Brasília. " +
	"Cada contexto compara seu primeiro preço elegível positivo no intervalo com o último preço elegível observado até a data, em pelo menos dois dias distintos, consecutivos ou não. " +
	"Exige o mesmo produto, anúncio, vendedor, loja, localidade e modalidade de compra. Cada contexto conta uma vez. " +
	"Calcula a média das variações dos contextos por loja, das lojas por produto e dos produtos, com pesos iguais em cada nível, sem arredondar etapas intermediárias. " +
	"A primeira data é uma referência de 0%, não uma variação medida. Antes do segundo preço de um contexto, ele fica fora do cálculo; preços futuros não preenchem datas anteriores. " +
	"Após o segundo preço, a comparação histórica continua incluída até uma nova observação elegível atualizar seu resultado. Isso não afirma que o preço permaneceu igual nos dias sem coleta. " +
	"A cobertura por data informa os participantes, os limites das datas realmente comparadas e quantos contextos receberam um novo preço elegível naquele dia. " +
	"Sem pares conhecidos até uma data, seu resultado fica vazio; um par posterior pode iniciar a comparação sem alterar o passado. " +
	"A amostra pode mudar e os pares podem cobrir períodos diferentes. Esta é uma média de variações observadas, não uma variação diária nem o produto de fatores diários. " +
	"Não interpola nem inventa preços em dias sem observação. Mantém as regras de elegibilidade de ofertas, embalagens e condições para todo o intervalo. " +
	"Essas regras podem depender do período e da composição atual dos grupos de equivalência. Condições desconhecidas são sinalizadas. O recorte monitorado não representa a inflação nacional. "

type OverviewMetadata struct {
	Counts            Coverage          `json:"counts"`
	DailyComparisons  []DailyComparison `json:"dailyComparisons"`
	UnknownConditions bool              `json:"unknownConditions"`
	CollectedAt       *time.Time        `json:"collectedAt"`
	AvailablePeriod   *Period           `json:"availablePeriod"`
	Locations         []string          `json:"locations"`
}

type OverviewCalculator struct {
	metadata    OverviewMetadata
	totals      map[string]*big.Rat
	comparisons map[string]DailyComparison
}

func NewOverview(metadata OverviewMetadata) *OverviewCalculator {
	calculator := &OverviewCalculator{metadata: metadata, totals: map[string]*big.Rat{}, comparisons: map[string]DailyComparison{}}
	for _, comparison := range metadata.DailyComparisons {
		calculator.comparisons[comparison.Date] = comparison
	}
	return calculator
}

// SQL combines only equal denominators; Go retains exact observed price ratios.
func (calculator *OverviewCalculator) Add(date, numerator, denominator string) error {
	value, valid := new(big.Rat).SetString(numerator)
	divisor, positive := new(big.Rat).SetString(denominator)
	if !valid || !positive || divisor.Sign() <= 0 {
		return fmt.Errorf("invalid overview weight")
	}
	value.Quo(value, divisor)
	total := calculator.totals[date]
	if total == nil {
		total = new(big.Rat)
	}
	calculator.totals[date] = total.Add(total, value)
	return nil
}

func (calculator *OverviewCalculator) Build(start, end string, now time.Time) History {
	history := calculator.history()
	if history.Counts.Products == 0 {
		return history
	}
	if history.AvailablePeriod != nil {
		start, end = history.AvailablePeriod.Start, history.AvailablePeriod.End
	}
	calculator.fillPoints(&history, calendarDates(start, end))
	setOverviewComparison(&history)
	finishContext(&history, now)
	history.Coverage = strings.Replace(history.Coverage, "incluídos na comparação", "incluídos em ao menos uma comparação observada", 1)
	history.Coverage += calculator.locations()
	return history
}

func (calculator *OverviewCalculator) fillPoints(history *History, dates []string) {
	for position, date := range dates {
		calculator.appendPoint(history, date, position)
	}
	history.Counts.Days = len(dates)
}

func (calculator *OverviewCalculator) appendPoint(history *History, date string, position int) {
	comparison := calculator.comparisons[date]
	comparison.Date = date
	comparison.ChangeBasisPoints = overviewChange(calculator.ratio(date, comparison.Products))
	point := Point{Date: date, Value: comparison.ChangeBasisPoints}
	if position == 0 && history.AvailablePeriod != nil {
		point.Value = rounded(new(big.Rat))
	}
	if position > 0 {
		history.DailyComparisons = append(history.DailyComparisons, comparison)
	}
	history.Points = append(history.Points, point)
	countPricedDay(history, point)
}

func (calculator *OverviewCalculator) ratio(date string, products int) *big.Rat {
	total := calculator.totals[date]
	if products == 0 || total == nil {
		return nil
	}
	return new(big.Rat).Quo(total, big.NewRat(int64(products)*10000, 1))
}

func overviewChange(ratio *big.Rat) *int64 {
	if ratio == nil {
		return nil
	}
	value := new(big.Rat).Sub(ratio, big.NewRat(1, 1))
	return rounded(value.Mul(value, big.NewRat(10000, 1)))
}

func (calculator *OverviewCalculator) locations() string {
	metadata := calculator.metadata
	sort.Strings(metadata.Locations)
	return " Localidades observadas: " + strings.Join(metadata.Locations, "; ") + "."
}

func (calculator *OverviewCalculator) history() History {
	metadata := calculator.metadata
	history := emptyHistory()
	history.Methodology = overviewMethodology + eligibilityMethodology
	history.Counts = metadata.Counts
	history.UnknownConditions = metadata.UnknownConditions
	history.CollectedAt = metadata.CollectedAt
	history.AvailablePeriod = metadata.AvailablePeriod
	return history
}

func setOverviewComparison(history *History) {
	if len(history.Points) < 2 {
		return
	}
	last := len(history.Points) - 1
	history.ChangeBasisPoints = history.Points[last].Value
	if history.ChangeBasisPoints == nil {
		return
	}
	comparisons := history.DailyComparisons
	comparison := comparisons[len(comparisons)-1]
	history.ComparisonStart, history.ComparisonEnd = comparison.ComparisonStart, comparison.ComparisonEnd
}
