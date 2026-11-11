package equivalence

import (
	"testing"

	"inflacao-real/core/internal/catalog"
)

func looseProduct(name string) Product {
	return Product{Name: name, Loose: true, Bases: []string{"kg"}}
}
func stringPointer(value string) *string { return &value }

func TestCommodityAliasesAndDepartments(test *testing.T) {
	first := looseProduct("Banana Maçã Kg")
	first.Brand = stringPointer("Hortifruti")
	second := looseProduct("Banana Maca KG")
	if CommodityKey(first) == "" || CommodityKey(first) != CommodityKey(second) {
		test.Fatal("department or accents prevented equivalent bananas")
	}
	nanica := looseProduct("Banana Nanica Kg")
	for _, name := range []string{"Banana Caturra Kg", "Banana Caturra/Nanica Kg"} {
		assertCommodityAlias(test, nanica, looseProduct(name))
	}
	meat := looseProduct("Carne Bovina Bife De Patinho Kg")
	meat.Brand = stringPointer("Açougue")
	if CommodityKey(meat) == "" {
		test.Fatal("department meat preparation not recognized")
	}
}

func TestCommodityUnknownAndBrandedRecordsStaySeparate(test *testing.T) {
	for _, name := range []string{"Banana Kg", "Banana Maçã Premium Kg", "Banana Maçã MarcaX Kg", "Alface Kg", "Patinho Temperado Kg", "Patinho Fresco Congelado Kg"} {
		assertNotCommodity(test, looseProduct(name))
	}
	product := looseProduct("Patinho Kg")
	product.Brand = stringPointer("Muffato Foods")
	if sameCommodity(product, looseProduct("Patinho Kg")) {
		test.Fatal("real brand treated as generic department")
	}
	product.Brand = stringPointer("Hortifruti")
	if CommodityKey(product) != "" {
		test.Fatal("department allowlist crossed categories")
	}
}

func TestCommoditySeparatesAttributes(test *testing.T) {
	names := []string{"Patinho Kg", "Patinho Inteiro Kg", "Patinho Bife Kg", "Patinho Tiras Kg", "Patinho Cubos Kg", "Patinho Moído Kg", "Patinho Orgânico Kg", "Patinho Congelado Kg", "Patinho Fresco Kg"}
	keys := map[string]bool{}
	for _, name := range names {
		recordDistinctCommodity(test, keys, name)
	}
	assertSeparateVarieties(test)
}

func assertSeparateVarieties(test *testing.T) {
	test.Helper()
	keys := map[string]bool{}
	for _, name := range []string{"Banana Maçã Kg", "Banana Prata Kg", "Banana Terra Kg", "Banana Nanica Kg"} {
		recordDistinctCommodity(test, keys, name)
	}
}

func TestCommodityRequiresMassAndConsistentListings(test *testing.T) {
	product := looseProduct("Banana Maçã Kg")
	product.Bases = []string{"unit"}
	if CommodityKey(product) != "" {
		test.Fatal("unit sale matched")
	}
	product.Bases = []string{"kg"}
	product.Package = &catalog.PackageSize{Quantity: "1", Unit: "kg", Count: 1}
	if CommodityKey(product) == "" {
		test.Fatal("known mass package excluded")
	}
	product.Package = nil
	product.Listings = []Listing{{Name: "Banana Prata Kg"}}
	if CommodityKey(product) != "" {
		test.Fatal("conflicting listing matched")
	}
}

func TestReviewFixturesAreNeverAutomaticallyGrouped(test *testing.T) {
	for _, name := range []string{"Alface Crespa Kg", "Alface Verde Kg", "Nescafé Solúvel Original Kg"} {
		assertNotCommodity(test, looseProduct(name))
	}
	product := looseProduct("Banana Maçã Kg")
	product.Brand = stringPointer("Nescafé")
	assertCommodityAlias(test, looseProduct("Banana Maçã Kg"), product)
}
func assertNotCommodity(test *testing.T, product Product) {
	test.Helper()
	if key := CommodityKey(product); key != "" {
		test.Fatal("review fixture auto recognized", key)
	}
}

func TestManualLooseReviewStillPreservesPreparation(test *testing.T) {
	first := looseProduct("Patinho Kg")
	for _, name := range []string{"Patinho Temperado Kg", "Patinho Moído Kg", "Patinho Congelado Kg", "Patinho Orgânico Kg"} {
		assertManualSeparation(test, first, looseProduct(name))
	}
}
func assertManualSeparation(test *testing.T, first, second Product) {
	test.Helper()
	if manualLooseComparable(first, second, true) {
		test.Fatal("manual review overrode preparation", second.Name)
	}
}

func assertCommodityAlias(test *testing.T, first, second Product) {
	test.Helper()
	if CommodityKey(first) == "" || CommodityKey(first) != CommodityKey(second) {
		test.Fatal("explicit alias lost", second.Name)
	}
}

func TestLiveBananaTitlesIgnoreBrandsAndSaleWeights(test *testing.T) {
	first := looseProduct("Banana Prata Kg")
	names := []string{"Banana Prata Aproximadamente 150g/un", "Fruta Banana Prata Bdj Kg",
		"Banana Prata 800g ( Qt. Aprox. 6 Un )", "Banana Prata Granel 700g (Aprox. 5 a 6 Unid)", "Banana prata 1,1kg", "Banana Prata 1k"}
	for _, name := range names {
		assertCommodityAlias(test, first, looseProduct(name))
	}
	for _, brand := range []string{"GERAL", "Direto do Produtor", "HORTIFRUTI", "Bandeiras"} {
		product := looseProduct("Banana Prata Kg")
		product.Brand = stringPointer(brand)
		assertCommodityAlias(test, first, product)
	}
}

func TestBananaOrganicAndLicensedGroupsPreserveClaims(test *testing.T) {
	organic := looseProduct("Banana Prata Orgânica Kg")
	for _, name := range []string{"Banana Prata Orgânica Santome 800g", "Banana Prata Org Bdj 500g",
		"Banana Prata Orgânica TAEQ 800g", "Banana Prata Orgânica RDU 800G", "Banana Prata Orgânica Qualyban 600g"} {
		assertCommodityAlias(test, organic, looseProduct(name))
	}
	licensed := looseProduct("Banana Prata Turma da Mônica 750g")
	assertCommodityAlias(test, licensed, looseProduct("Banana Prata Turma da Monica 0,75kg"))
	if CommodityKey(organic) == CommodityKey(licensed) || CommodityKey(licensed) == CommodityKey(looseProduct("Banana Prata Kg")) {
		test.Fatal("organic, conventional and licensed bananas were combined")
	}
	label := commodityLabel(licensed)
	if label == nil || *label != "Banana prata Turma da Mônica" {
		test.Fatal("licensed label lost", label)
	}
}

func TestCommodityPackagesUseMassOnly(test *testing.T) {
	first := looseProduct("Banana Prata Kg")
	second := Product{Name: "Banana Prata 750g", Package: &catalog.PackageSize{Quantity: "750", Unit: "g", Count: 2}, Bases: []string{"package"}}
	assertCommodityAlias(test, first, second)
	second.Package = nil
	second.Name = "Banana prata 1,1kg"
	assertCommodityAlias(test, first, second)
	second.Name = "Banana Prata"
	assertNotCommodity(test, second)
	second.Bases = []string{"unit"}
	assertNotCommodity(test, second)
	second.Package = &catalog.PackageSize{Quantity: "1", Unit: "unit", Count: 1}
	assertNotCommodity(test, second)
}

func TestBrandLabelsCannotEraseProduceAttributes(test *testing.T) {
	for _, attribute := range []string{"Orgânico", "Baby", "Turma da Mônica"} {
		product := looseProduct("Banana Prata " + attribute + " Kg")
		product.Brand = stringPointer(attribute)
		assertRecognizedSeparation(test, product, looseProduct("Banana Prata Kg"))
	}
}

func TestMeatCutsMatchAcrossMassAndRetailerLabels(test *testing.T) {
	pairs := [][2]string{
		{"Carne Bovina Moída Acém Kg", "Acém Moído 500g"},
		{"Carne Acem Com Osso", "Acém com Osso Kg"},
		{"Acém Bovino sem Osso Kg", "Acém s/ Osso 1kg"},
		{"Acém Bovino Resfriado Pedaço Bandeja 1kg", "Acém Resfriado Pedaço 1,1kg"},
		{"Carne Moída de Acém Bovina Resfriada Kg", "Carne Moída De Acém Bovina Resfriada 500g"},
		{"Picanha Bovina Resfriada 1kg", "Picanha Resfriada 750g"},
		{"Carne Moída Kg", "Carne Moida 500g"},
	}
	for _, pair := range pairs {
		first, second := looseProduct(pair[0]), looseProduct(pair[1])
		first.Brand, second.Brand = stringPointer("Açougue"), stringPointer("Bovino in Natura")
		assertCommodityAlias(test, first, second)
	}
}

func TestMeatSpeciesCutsPreparationAndBoneRemainSeparate(test *testing.T) {
	pairs := [][2]string{{"Carne Moída", "Carne Bovina Moída"}, {"Carne Moída", "Acém Moído"},
		{"Acém Moído", "Patinho Moído"}, {"Acém", "Miolo de Acém"}, {"Acém", "Acém Moído"},
		{"Acém", "Acém com Osso"}, {"Acém sem Osso", "Acém com Osso"},
		{"Picanha", "Picanha Suína"}, {"Picanha", "Picanha Angus"},
		{"Picanha Resfriada", "Picanha Congelada"}, {"Picanha", "Picanha Bife"}}
	for _, pair := range pairs {
		first, second := looseProduct(pair[0]+" Kg"), looseProduct(pair[1]+" Kg")
		assertRecognizedSeparation(test, first, second)
	}
}

func assertRecognizedSeparation(test *testing.T, first, second Product) {
	test.Helper()
	if CommodityKey(first) == "" || CommodityKey(second) == "" || sameCommodity(first, second) {
		test.Fatal("commodity variants not distinguished", first.Name, second.Name)
	}
}

func TestBrandedMeatConvertsWeightsWithinTheSameBrand(test *testing.T) {
	first := looseProduct("Acém Friboi Moído Resfriado Kg")
	first.Brand = stringPointer("Friboi")
	second := Product{Name: "Acém Friboi Moído Resfriado 500g", Brand: stringPointer("FRIBOI"),
		Package: &catalog.PackageSize{Quantity: "500", Unit: "g", Count: 1}, Bases: []string{"package"}}
	assertCommodityAlias(test, first, second)
	second.Brand = stringPointer("Swift")
	second.Name = "Acém Swift Moído Resfriado 500g"
	if sameCommodity(first, second) || sameCommodity(first, looseProduct("Acém Moído Resfriado Kg")) {
		test.Fatal("named meat brands erased")
	}
	if label := commodityLabel(first); label == nil || *label != "Acém moído resfriado · Friboi" {
		test.Fatal("meat brand missing from group label", label)
	}
}

func TestProcessedFlavoredAndContradictoryMeatIsNotAutomatic(test *testing.T) {
	for _, name := range []string{"Picanha Suína Manteiga e Ervas Aurora Kg", "Picanha Temperada Kg", "Batata Picanha 100g",
		"Linguiça de Picanha Suína Kg", "Carne moída arroz integral e feijão Kg", "Picanha Resfriada Congelada Kg", "Acém com Osso sem Osso Kg"} {
		assertNotCommodity(test, looseProduct(name))
	}
}
func recordDistinctCommodity(test *testing.T, keys map[string]bool, name string) {
	test.Helper()
	key := CommodityKey(looseProduct(name))
	if key == "" || keys[key] {
		test.Fatal("attributes combined", name, key)
	}
	keys[key] = true
}
