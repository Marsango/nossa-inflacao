package equivalence

import (
	"regexp"
	"strings"

	"inflacao-real/core/internal/catalog"
)

const RuleVersion = "commodities_v2"

type commodityRule struct {
	name, department string
	aliases          []string
}

var commodityRules = []commodityRule{
	{"banana-nanica", "produce", []string{"banana nanica", "banana caturra", "banana caturra nanica"}},
	{"banana-maca", "produce", []string{"banana maca"}},
	{"banana-prata", "produce", []string{"banana prata"}},
	{"banana-terra", "produce", []string{"banana da terra", "banana terra"}},
	{"batata-inglesa", "produce", []string{"batata inglesa"}},
	{"batata", "produce", []string{"batata"}},
	{"tomate", "produce", []string{"tomate"}},
	{"tomate-italiano", "produce", []string{"tomate italiano"}},
	{"tomate-cereja", "produce", []string{"tomate cereja"}},
	{"cebola", "produce", []string{"cebola"}},
	{"cebola-roxa", "produce", []string{"cebola roxa"}},
	{"cenoura", "produce", []string{"cenoura"}},
	{"acem", "meat", []string{"acem"}},
	{"miolo-acem", "meat", []string{"miolo de acem", "miolo acem"}},
	{"picanha-suina", "meat", []string{"picanha suina"}},
	{"picanha", "meat", []string{"picanha"}},
	{"musculo", "meat", []string{"musculo"}},
	{"carne-moida-bovina", "meat", []string{"carne bovina moida", "carne moida bovina", "carne moida de bovino"}},
	{"carne-moida", "meat", []string{"carne moida"}},
	{"patinho", "meat", []string{"patinho", "patinho bovino"}},
	{"coxao-mole", "meat", []string{"coxao mole", "cha de dentro"}},
	{"coxao-duro", "meat", []string{"coxao duro", "cha de fora"}},
}

// CommodityKey consumes every word. Unrecognized wording never establishes identity.
func CommodityKey(product Product) string {
	if !massComparable(product) {
		return ""
	}
	key := commodityName(product.Name, product.Brand)
	if key == "" {
		return ""
	}
	if !consistentListings(product.Listings, key) {
		return ""
	}
	return key
}

func massComparable(product Product) bool {
	if product.Package != nil && product.Package.Unit != "kg" && product.Package.Unit != "g" {
		return false
	}
	comparable := len(product.Bases) > 0
	for _, basis := range product.Bases {
		comparable = comparable && massBasis(product, basis)
	}
	return comparable
}

func massBasis(product Product, basis string) bool {
	if basis == "kg" {
		return true
	}
	return basis == "package" && (product.Package != nil || declaredTitleMass.MatchString(product.Name))
}

func sameCommodity(first, second Product) bool {
	key := CommodityKey(first)
	return key != "" && key == CommodityKey(second)
}

func commodityName(name string, brand *string) string {
	normalized := commodityTitle(name, brand)
	key := ""
	for _, rule := range commodityRules {
		key = firstKey(key, rule.match(normalized, brand))
	}
	return key
}

func (rule commodityRule) match(name string, brand *string) string {
	if !departmentBrand(brand, rule.department) {
		return ""
	}
	key := ""
	for _, alias := range rule.aliases {
		key = firstKey(key, rule.matchAlias(name, alias, brand))
	}
	return key
}

func departmentBrand(brand *string, department string) bool {
	if department == "produce" {
		return true
	}
	if brand == nil || catalog.NormalizeText(*brand) == "" {
		return true
	}
	return department == "meat" && !strings.Contains(catalog.NormalizeText(*brand), "hortifruti")
}

func (rule commodityRule) matchAlias(name, alias string, brand *string) string {
	remaining, found := removePhrase(name, alias)
	if !found {
		return ""
	}
	if rule.name == "carne-moida" && familyWords(remaining, "bovino bovina suino suina frango") != "" {
		return ""
	}
	attributes, valid := commodityAttributes(remaining, rule.department)
	if !valid {
		return ""
	}
	return RuleVersion + ":" + rule.name + ":" + attributes + ":kg" + meatBrandSuffix(rule.department, brand)
}

func meatBrandSuffix(department string, brand *string) string {
	if department != "meat" || genericMeatBrand(brand) {
		return ""
	}
	return ":" + catalog.NormalizeText(*brand)
}

func genericMeatBrand(brand *string) bool {
	if brand == nil {
		return true
	}
	name := catalog.NormalizeText(*brand)
	return name == "" || name == "acougue" || name == "bovino in natura" || name == "geral" || name == "bandeiras" || name == "direto do produtor"
}

func removePhrase(name, phrase string) (string, bool) {
	padded := " " + name + " "
	target := " " + phrase + " "
	if !strings.Contains(padded, target) {
		return "", false
	}
	return strings.TrimSpace(strings.Replace(padded, target, " ", 1)), true
}

type commodityAttributesParser struct {
	preparation string
	claims      []string
	valid       bool
}

func commodityAttributes(value, department string) (string, bool) {
	parser := commodityAttributesParser{preparation: "unspecified", valid: true}
	for _, word := range strings.Fields(value) {
		parser.consume(word, department)
	}
	signature := catalog.NameSignature(strings.Join(parser.claims, " "))
	if conflictingCommodityClaims(signature) {
		return "", false
	}
	return parser.preparation + ":" + signature, parser.valid
}

func conflictingCommodityClaims(signature string) bool {
	return (strings.Contains(signature, "frozen") && (strings.Contains(signature, "fresh") || strings.Contains(signature, "chilled"))) ||
		(strings.Contains(signature, "bonein") && strings.Contains(signature, "boneless"))
}
func (parser *commodityAttributesParser) consume(word, department string) {
	next, claim, accepted := commodityWord(word, department)
	if !accepted || (next != "" && parser.preparation != "unspecified" && next != parser.preparation) {
		parser.valid = false
		return
	}
	if next != "" {
		parser.preparation = next
	}
	if claim != "" {
		parser.claims = append(parser.claims, claim)
	}
}
func consistentListings(listings []Listing, key string) bool {
	consistent := true
	for _, listing := range listings {
		consistent = consistent && commodityName(listing.Name, listing.Brand) == key
	}
	return consistent
}
func firstKey(current, next string) string {
	if current != "" {
		return current
	}
	return next
}

func commodityWord(word, department string) (string, string, bool) {
	if department == "produce" {
		return produceWord(word)
	}
	if department == "meat" && (word == "carne" || word == "bovina" || word == "bovino" || word == "de") {
		return "", "", true
	}
	if word == "kg" || word == "quilo" {
		return "", "", true
	}
	if word == "organico" || word == "organica" {
		return "", "organic", true
	}
	if word == "congelado" || word == "congelada" {
		return "", "frozen", true
	}
	return meatPreparation(word, department)
}

var titleMass = regexp.MustCompile(`(?i)\b[0-9]+(?:[.,][0-9]+)?\s*(?:kg|g|k)\b(?:\s*/\s*(?:un|unid|unidade))?`)
var declaredTitleMass = regexp.MustCompile(`(?i)^[^0-9]*\b[0-9]+(?:[.,][0-9]{1,6})?\s*(?:kg|g|k)\s*$`)
var approximateCount = regexp.MustCompile(`(?i)\(\s*(?:qt\.?\s*)?(?:aprox\.?|aproximadamente)\s*[0-9]+(?:\s*a\s*[0-9]+)?\s*(?:un|unid|unidades?)\s*\)`)

func commodityTitle(name string, brand *string) string {
	name = approximateCount.ReplaceAllString(name, " ")
	name = titleMass.ReplaceAllString(name, " ")
	name = catalog.NormalizeText(name)
	name = strings.ReplaceAll(name, "turma da monica", "turmadamonica")
	replacer := strings.NewReplacer("sem osso", "boneless", "s osso", "boneless", "com osso", "bonein")
	name = replacer.Replace(name)
	if removableCommodityBrand(brand) {
		name = removeOptionalPhrase(name, catalog.NormalizeText(*brand))
	}
	return name
}

func removableCommodityBrand(brand *string) bool {
	if brand == nil {
		return false
	}
	name := catalog.NormalizeText(*brand)
	protected := "banana maca prata terra nanica caturra batata tomate italiano cereja cebola roxa cenoura patinho coxao mole duro acem picanha musculo baby turma monica organico organica org fresco fresca congelado congelada resfriado resfriada angus osso"
	return familyWords(name, protected) == ""
}

func produceWord(word string) (string, string, bool) {
	ignored := " kg quilo fruta bdj bandeja granel aproximadamente aprox geral hortifruti hortifrutigranjeiros santome taeq rdu qualyban "
	if strings.Contains(ignored, " "+word+" ") {
		return "", "", true
	}
	claims := map[string]string{"organico": "organic", "organica": "organic", "org": "organic",
		"fresco": "fresh", "fresca": "fresh", "congelado": "frozen", "congelada": "frozen",
		"baby": "baby", "turmadamonica": "licensed"}
	claim, accepted := claims[word]
	return "", claim, accepted
}

func commodityLabel(product Product) *string {
	parts := strings.Split(CommodityKey(product), ":")
	if len(parts) < 5 {
		return nil
	}
	name := commodityDisplayName(parts[1])
	for _, attribute := range strings.Fields(parts[2] + " " + parts[3]) {
		name += commodityLabelAttribute(attribute, parts[1])
	}
	name = strings.ToUpper(name[:1]) + name[1:]
	name += commodityBrandLabel(product.Brand, len(parts))
	return &name
}

func commodityDisplayName(key string) string {
	names := map[string]string{"banana-maca": "banana maçã", "coxao-mole": "coxão mole", "coxao-duro": "coxão duro",
		"acem": "acém", "miolo-acem": "miolo de acém", "musculo": "músculo", "carne-moida": "carne moída", "carne-moida-bovina": "carne bovina moída", "picanha-suina": "picanha suína"}
	if name := names[key]; name != "" {
		return name
	}
	return strings.ReplaceAll(key, "-", " ")
}

func commodityBrandLabel(brand *string, parts int) string {
	if parts > 5 && brand != nil {
		return " · " + *brand
	}
	return ""
}

func commodityLabelAttribute(attribute, key string) string {
	labels := map[string]string{"organic": "orgânico", "fresh": "fresco", "frozen": "congelado", "baby": "baby",
		"licensed": "Turma da Mônica", "whole": "inteiro", "piece": "pedaço", "steak": "bife", "strips": "tiras", "cubes": "cubos", "ground": "moído",
		"chilled": "resfriado", "boneless": "sem osso", "bonein": "com osso", "angus": "Angus"}
	if label := labels[attribute]; label != "" {
		return " " + genderedCommodityLabel(label, attribute, key)
	}
	return ""
}

func genderedCommodityLabel(label, attribute, key string) string {
	feminine := strings.HasPrefix(key, "banana") || strings.HasPrefix(key, "batata") || strings.HasPrefix(key, "cebola") ||
		strings.HasPrefix(key, "cenoura") || strings.HasPrefix(key, "picanha") || strings.HasPrefix(key, "carne")
	adjective := strings.Contains(" organic fresh frozen chilled whole ground ", " "+attribute+" ")
	if feminine && adjective {
		return strings.TrimSuffix(label, "o") + "a"
	}
	return label
}

func removeOptionalPhrase(name, phrase string) string {
	remaining, found := removePhrase(name, phrase)
	if found {
		return remaining
	}
	return name
}

func meatPreparation(word, department string) (string, string, bool) {
	if word == "fresco" || word == "fresca" {
		return "", "fresh", true
	}
	claims := map[string]string{"resfriado": "chilled", "resfriada": "chilled", "boneless": "boneless", "bonein": "bonein", "angus": "angus"}
	if department == "meat" && claims[word] != "" {
		return "", claims[word], true
	}
	if department == "meat" && strings.Contains(" em bandeja bdj aproximadamente aprox ", " "+word+" ") {
		return "", "", true
	}
	preparations := map[string]string{"inteiro": "whole", "inteira": "whole", "peca": "piece", "pedaco": "piece", "pedacos": "piece", "bife": "steak", "bifes": "steak", "tiras": "strips", "cubos": "cubes", "moido": "ground", "moida": "ground"}
	if department == "meat" && preparations[word] != "" {
		return preparations[word], "", true
	}
	return "", "", false
}
