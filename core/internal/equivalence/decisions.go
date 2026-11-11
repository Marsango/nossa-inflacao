package equivalence

import (
	"context"
	"database/sql"
	"encoding/json"
	"strings"

	"inflacao-real/core/internal/catalog"
)

const CatalogLock = `SELECT pg_advisory_xact_lock(694120031)`

type change struct {
	requestContext context.Context
	transaction    *sql.Tx
	decision       Decision
	actor          string
	rule           *string
	catalog        []Product
}

func Apply(requestContext context.Context, database *sql.DB, actor string, decision Decision) error {
	if strings.TrimSpace(decision.Reason) == "" || len(decision.Reason) > 2000 {
		return ErrInvalid
	}
	transaction, err := database.BeginTx(requestContext, nil)
	if err != nil {
		return err
	}
	defer transaction.Rollback()
	mutation := change{requestContext: requestContext, transaction: transaction, decision: decision, actor: actor}
	if err := mutation.lock(); err != nil {
		return err
	}
	if err := mutation.record(); err != nil {
		return err
	}
	return transaction.Commit()
}

func (mutation change) lock() error {
	if _, err := mutation.transaction.ExecContext(mutation.requestContext, CatalogLock); err != nil {
		return err
	}
	var revision int64
	err := mutation.transaction.QueryRowContext(mutation.requestContext, `SELECT revision FROM catalog_decisions`).Scan(&revision)
	if err != nil {
		return err
	}
	if revision != mutation.decision.Revision {
		return ErrStale
	}
	return nil
}

func (mutation change) record() error {
	before, err := membership(mutation.requestContext, mutation.transaction)
	if err != nil {
		return err
	}
	if err := mutation.perform(); err != nil {
		return err
	}
	after, err := membership(mutation.requestContext, mutation.transaction)
	if err != nil {
		return err
	}
	return mutation.audit(before, after)
}

func membership(requestContext context.Context, database queryer) (json.RawMessage, error) {
	var result json.RawMessage
	err := database.QueryRowContext(requestContext, `SELECT COALESCE(jsonb_agg(e ORDER BY product_id),'[]') FROM product_equivalence e`).Scan(&result)
	return result, err
}

func (mutation change) audit(before, after json.RawMessage) error {
	var revision int64
	err := mutation.transaction.QueryRowContext(mutation.requestContext, `UPDATE catalog_decisions SET revision=revision+1 RETURNING revision`).Scan(&revision)
	if err != nil {
		return err
	}
	decision := mutation.decision
	encoded, err := json.Marshal(decision)
	if err != nil {
		return err
	}
	_, err = mutation.transaction.ExecContext(mutation.requestContext, `INSERT INTO equivalence_audit
  (actor,action,reason,rule_version,revision,before_membership,after_membership,decision) VALUES($1,$2,$3,$4,$5,$6,$7,$8)`,
		mutation.actor, decision.Action, decision.Reason, mutation.rule, revision, []byte(before), []byte(after), encoded)
	return err
}

func (mutation change) perform() error {
	switch mutation.decision.Action {
	case "approve":
		return mutation.approve()
	case "reject":
		return mutation.reject()
	case "remove":
		return mutation.remove()
	case "dissolve":
		return mutation.dissolve()
	case "representative":
		return mutation.representative()
	case "activate":
		return mutation.activate(true)
	case "deactivate":
		return mutation.activate(false)
	}
	return ErrInvalid
}

func (mutation change) activate(enabled bool) error {
	if _, err := mutation.transaction.ExecContext(mutation.requestContext, `UPDATE catalog_decisions SET generic_enabled=$1`, enabled); err != nil {
		return err
	}
	if enabled {
		return Reconcile(mutation.requestContext, mutation.transaction)
	}
	return nil
}

func (mutation change) pair() (Product, Product, error) {
	products, err := mutation.loadProducts()
	if err != nil {
		return Product{}, Product{}, err
	}
	index := productIndex(products)
	first, second := index[mutation.decision.First], index[mutation.decision.Second]
	if first.ID == 0 || second.ID == 0 || first.ID == second.ID {
		return first, second, ErrInvalid
	}
	return first, second, nil
}

func (mutation change) loadProducts() ([]Product, error) {
	if mutation.catalog != nil {
		return mutation.catalog, nil
	}
	return Load(mutation.requestContext, mutation.transaction)
}

func (mutation change) approve() error {
	first, second, err := mutation.pair()
	if err != nil {
		return err
	}
	if first.Representative == second.Representative {
		return ErrStale
	}
	if !mergeComparable(first, second) && !manualLooseComparable(first, second, mutation.decision.SourceVerified) {
		return ErrInvalid
	}
	if requiresVerification(first, second) && !mutation.decision.SourceVerified {
		return ErrInvalid
	}
	if err := mutation.validateGroups(first, second); err != nil {
		return err
	}
	return mutation.merge(first, second)
}

func mergeComparable(first, second Product) bool {
	if sameCommodity(first, second) {
		return true
	}
	return brandedComparable(first, second) && !conflictingVariants(first.Name, second.Name)
}

func (mutation change) merge(first, second Product) error {
	if err := mutation.requireNoExclusion(first, second); err != nil {
		return err
	}
	var representative int64
	err := mutation.transaction.QueryRowContext(mutation.requestContext, `SELECT min(id) FROM products
 WHERE id IN ($1,$2) OR id IN (SELECT product_id FROM product_equivalence WHERE representative_id IN ($1,$2))`,
		first.Representative, second.Representative).Scan(&representative)
	if err != nil {
		return err
	}
	return mutation.mergeMembership(first, second, representative)
}

func (mutation change) mergeMembership(first, second Product, representative int64) error {
	_, err := mutation.transaction.ExecContext(mutation.requestContext, `INSERT INTO product_equivalence(product_id,representative_id,comparison_basis,comparison_name)
 SELECT id,$3,$4,$5 FROM products WHERE id IN ($1,$2)
 OR id IN (SELECT product_id FROM product_equivalence WHERE representative_id IN ($1,$2))
 ON CONFLICT(product_id) DO UPDATE SET representative_id=EXCLUDED.representative_id,
 comparison_basis=EXCLUDED.comparison_basis,comparison_name=EXCLUDED.comparison_name`,
		first.Representative, second.Representative, representative, comparisonBasis(first, second), comparisonName(first, second))
	if err == nil {
		mutation.updateMembers(first, second, representative)
	}
	return err
}

func (mutation change) updateMembers(first, second Product, representative int64) {
	for position, product := range mutation.catalog {
		mutation.catalog[position].Representative = mergedRepresentative(product, first, second, representative)
	}
}

func mergedRepresentative(product, first, second Product, representative int64) int64 {
	if product.Representative == first.Representative || product.Representative == second.Representative {
		return representative
	}
	return product.Representative
}

func comparisonName(first, second Product) *string {
	if sameCommodity(first, second) {
		return commodityLabel(first)
	}
	return nil
}

func comparisonBasis(first, second Product) *string {
	if sameCommodity(first, second) {
		basis := "kg"
		return &basis
	}
	return nil
}

func requiresVerification(first, second Product) bool {
	if sameCommodity(first, second) {
		return false
	}
	candidate, _ := Suggest(first, second)
	return candidate.VerificationRequired
}
func (mutation change) requireNoExclusion(first, second Product) error {
	var blocked bool
	err := mutation.transaction.QueryRowContext(mutation.requestContext, `SELECT EXISTS(SELECT 1 FROM product_exclusions
 WHERE equivalent_product_id(first_id) IN ($1,$2) AND equivalent_product_id(second_id) IN ($1,$2))`, first.Representative, second.Representative).Scan(&blocked)
	if err != nil {
		return err
	}
	if blocked {
		return ErrInvalid
	}
	return nil
}

func (mutation change) reject() error {
	first, second, err := mutation.pair()
	if err != nil {
		return err
	}
	if first.Representative == second.Representative {
		return ErrInvalid
	}
	_, err = mutation.transaction.ExecContext(mutation.requestContext, `INSERT INTO product_exclusions(first_id,second_id)
  VALUES(LEAST($1::bigint,$2::bigint),GREATEST($1::bigint,$2::bigint)) ON CONFLICT DO NOTHING`, first.ID, second.ID)
	return err
}

func manualLooseComparable(first, second Product, verified bool) bool {
	if !verified || !first.Loose || !second.Loose || first.Package != nil || second.Package != nil {
		return false
	}
	if len(first.Bases) != 1 || first.Bases[0] != "kg" || !sameBases(first.Bases, second.Bases) {
		return false
	}
	left, right := CommodityKey(first), CommodityKey(second)
	if left != "" && right != "" && left != right {
		return false
	}
	return !conflictingVariants(first.Name, second.Name) && genericReviewAttributes(first.Name) == genericReviewAttributes(second.Name)
}

func productIndex(products []Product) map[int64]Product {
	index := map[int64]Product{}
	for _, product := range products {
		index[product.ID] = product
	}
	return index
}

func genericReviewAttributes(name string) string {
	return familyWords(catalog.NormalizeText(name), "maca prata terra nanica caturra patinho coxao mole duro acem picanha musculo miolo bovino bovina suino suina frango osso com sem angus resfriado resfriada pedaco pedacos peca bife bifes inteiro inteira moido moida tiras cubos organico organica congelado congelada fresco fresca temperado temperada empanado empanada cozido cozida assado assada defumado defumada")
}
